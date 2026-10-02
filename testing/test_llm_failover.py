"""
Multi-provider failover (app/openai_client.py + intent_extractor._create_completion_with_retry).

All providers are fakes; no network. Policy under test:
  * daily-quota 429 -> park provider, fail over immediately, no retry
  * per-minute 429  -> at most one short retry (Retry-After honored), then fail over
  * 5xx / connection / other 4xx -> fail over
  * rate_limited is raised only when every configured provider is rate limited
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import app.intent_extractor as extractor
import app.openai_client as client_module
from app.intent_extractor import IntentExtractionError
from testing.llm_fakes import (
    FakeCompletions,
    Usage,
    auth_error,
    connection_error,
    daily_quota_error,
    rate_limit_error,
    server_error,
    use_providers,
)

SCHEMA_CONTEXT = {"tables": ["customers"], "columns": {"customers": ["customer_id"]}}


@pytest.fixture
def sleeps(monkeypatch):
    recorded = []
    monkeypatch.setattr(extractor.time, "sleep", recorded.append)
    return recorded


def _ask():
    return extractor.extract_intent("show customers", SCHEMA_CONTEXT)


# ---------------------------------------------------------------------- #
# Required cases
# ---------------------------------------------------------------------- #

def test_provider_1_rate_limited_succeeds_on_provider_2(monkeypatch, sleeps, caplog):
    """(a) provider-1 429 -> answered by provider-2."""
    first = FakeCompletions(errors=[rate_limit_error(), rate_limit_error()])
    second = FakeCompletions(usage=Usage(prompt_tokens=321, completion_tokens=54))
    use_providers(monkeypatch, gemini=first, groq=second)

    with caplog.at_level(logging.INFO, logger="app.intent_extractor"):
        intent = _ask()

    assert intent.tables == ["customers"]
    assert first.calls == 2   # call + one short retry, then fail over
    assert second.calls == 1
    assert len(sleeps) == 1
    served = [r.getMessage() for r in caplog.records if "LLM request served" in r.getMessage()]
    assert served == [
        "LLM request served provider=groq model=groq-test-model prompt_tokens=321 completion_tokens=54"
    ]


def test_daily_quota_fails_over_immediately_without_retry(monkeypatch, sleeps):
    """(b) TPD-style 429 -> no retry loop, provider parked, straight to the next one."""
    first = FakeCompletions(errors=[daily_quota_error()])
    second = FakeCompletions()
    use_providers(monkeypatch, gemini=first, groq=second)

    _ask()

    assert first.calls == 1
    assert second.calls == 1
    assert sleeps == []

    # Parked: the next request does not even try the exhausted provider.
    _ask()
    assert first.calls == 1
    assert second.calls == 2


# ---------------------------------------------------------------------- #
# Rest of the policy
# ---------------------------------------------------------------------- #

def test_daily_quota_cooldown_comes_from_the_providers_hint(monkeypatch, sleeps):
    use_providers(monkeypatch, gemini=FakeCompletions(errors=[daily_quota_error("3m53.28s")]),
                  groq=FakeCompletions())
    _ask()
    remaining = client_module._exhausted_until["gemini"] - client_module.time.monotonic()
    assert remaining == pytest.approx(233.28, abs=5)


def test_parked_provider_is_tried_again_after_its_cooldown(monkeypatch, sleeps):
    first = FakeCompletions(errors=[daily_quota_error("10s")])
    use_providers(monkeypatch, gemini=first, groq=FakeCompletions())
    _ask()

    client_module._exhausted_until["gemini"] = client_module.time.monotonic() - 1  # cooldown over
    _ask()
    assert first.calls == 2


@pytest.mark.parametrize("message", [
    "Rate limit reached on tokens per day (TPD): Limit 200000",
    "Quota exceeded for metric GenerateRequestsPerDayPerProjectPerModel-FreeTier",
    "You exceeded your daily limit",
    "requests per day (RPD): Limit 1000",
])
def test_daily_quota_wordings_are_recognised(message):
    assert extractor._is_daily_quota(rate_limit_error(message=message))


@pytest.mark.parametrize("message", [
    "Rate limit reached on tokens per minute (TPM): Limit 8000",
    "Requests rate limit exceeded",
])
def test_per_minute_limits_are_not_daily(message):
    assert not extractor._is_daily_quota(rate_limit_error(message=message))


def test_all_providers_rate_limited_raises_rate_limited(monkeypatch, sleeps):
    use_providers(
        monkeypatch,
        gemini=FakeCompletions(errors=[daily_quota_error("1h2m3s")]),
        groq=FakeCompletions(errors=[rate_limit_error("2"), rate_limit_error("2")]),
    )

    with pytest.raises(IntentExtractionError) as excinfo:
        _ask()

    assert excinfo.value.kind == "rate_limited"
    assert excinfo.value.retry_after == 2


def test_when_every_provider_is_parked_no_call_is_made(monkeypatch, sleeps):
    first = FakeCompletions(errors=[daily_quota_error("10m")])
    second = FakeCompletions(errors=[daily_quota_error("4m")])
    use_providers(monkeypatch, gemini=first, groq=second)
    with pytest.raises(IntentExtractionError):
        _ask()

    with pytest.raises(IntentExtractionError) as excinfo:
        _ask()

    assert excinfo.value.kind == "rate_limited"
    assert 200 < excinfo.value.retry_after <= 240  # the soonest provider comes back in ~4 minutes
    assert first.calls == 1 and second.calls == 1


def test_long_retry_after_fails_over_without_waiting(monkeypatch, sleeps):
    first = FakeCompletions(errors=[rate_limit_error(retry_after="45")])
    second = FakeCompletions()
    use_providers(monkeypatch, gemini=first, groq=second)

    _ask()

    assert sleeps == []
    assert first.calls == 1 and second.calls == 1


def test_server_error_fails_over_without_retry(monkeypatch, sleeps):
    first = FakeCompletions(errors=[server_error()])
    second = FakeCompletions()
    use_providers(monkeypatch, gemini=first, groq=second)

    _ask()

    assert first.calls == 1 and second.calls == 1 and sleeps == []


def test_misconfigured_provider_does_not_take_the_endpoint_down(monkeypatch, sleeps):
    # A wrong key on the first provider must not break /query while others work.
    use_providers(monkeypatch, gemini=FakeCompletions(errors=[auth_error()]), groq=FakeCompletions())
    assert _ask().tables == ["customers"]


def test_mixed_failures_are_reported_as_unavailable(monkeypatch, sleeps):
    use_providers(
        monkeypatch,
        gemini=FakeCompletions(errors=[daily_quota_error()]),
        groq=FakeCompletions(errors=[connection_error()]),
    )
    with pytest.raises(IntentExtractionError) as excinfo:
        _ask()
    assert excinfo.value.kind == "unavailable"


def test_only_bad_responses_are_reported_as_invalid(monkeypatch, sleeps):
    use_providers(monkeypatch, gemini=FakeCompletions(errors=[auth_error()]),
                  groq=FakeCompletions(arguments="{nope"))
    with pytest.raises(IntentExtractionError) as excinfo:
        _ask()
    assert excinfo.value.kind == "invalid_response"


def test_unusable_answer_fails_over(monkeypatch, sleeps):
    first = FakeCompletions(content="Sure! Here are your customers.")  # no tool call, not JSON
    second = FakeCompletions()
    use_providers(monkeypatch, gemini=first, groq=second)

    _ask()

    assert first.calls == 1 and second.calls == 1


def test_json_in_message_content_is_accepted(monkeypatch, sleeps):
    # Gemini runs with tool_choice="auto" and may answer in the message body.
    gemini = FakeCompletions(content='```json\n{"query_type": "select", "tables": ["customers"]}\n```')
    use_providers(monkeypatch, gemini=gemini, groq=FakeCompletions())

    assert _ask().tables == ["customers"]
    assert gemini.calls == 1


def test_each_provider_gets_its_model_and_tool_choice(monkeypatch, sleeps):
    gemini = FakeCompletions(errors=[server_error()])
    groq = FakeCompletions()
    use_providers(monkeypatch, gemini=gemini, groq=groq)

    _ask()

    assert (gemini.requests[0]["model"], gemini.requests[0]["tool_choice"]) == ("gemini-test-model", "auto")
    assert (groq.requests[0]["model"], groq.requests[0]["tool_choice"]) == ("groq-test-model", "required")
    for completions in (gemini, groq):
        assert completions.requests[0]["max_tokens"] == 800
        assert "functions" not in completions.requests[0]


def test_no_provider_configured_is_a_clear_error(monkeypatch):
    use_providers(monkeypatch)  # none
    with pytest.raises(IntentExtractionError, match="API key not found"):
        _ask()


# ---------------------------------------------------------------------- #
# Configuration
# ---------------------------------------------------------------------- #

def _set_keys(monkeypatch, *names):
    from testing.llm_fakes import clear_provider_env
    clear_provider_env(monkeypatch)
    for name in names:
        monkeypatch.setenv(client_module.PROVIDERS[name].key_env, "k")


def test_default_order_skips_providers_without_keys(monkeypatch):
    _set_keys(monkeypatch, "groq", "gemini")
    assert [p.name for p in client_module.configured_providers()] == ["gemini", "groq"]


def test_groq_only_deployment_keeps_working(monkeypatch):
    _set_keys(monkeypatch, "groq")
    providers = client_module.configured_providers()
    assert [(p.name, p.model) for p in providers] == [("groq", "qwen/qwen3.8-27b")]


def test_order_is_configurable_and_unknown_names_are_ignored(monkeypatch):
    _set_keys(monkeypatch, "groq", "gemini")
    monkeypatch.setenv("LLM_PROVIDER_ORDER", " groq, nonsense ,GEMINI,groq")
    assert [p.name for p in client_module.configured_providers()] == ["groq", "gemini"]


@pytest.mark.parametrize("dropped", ["mistral", "cerebras", "openai"])
def test_dropped_providers_are_not_supported(monkeypatch, dropped):
    # Mistral and Cerebras need a payment method to activate; the chain is gemini,groq only.
    _set_keys(monkeypatch, "groq")
    monkeypatch.setenv(f"{dropped.upper()}_API_KEY", "k")
    monkeypatch.setenv("LLM_PROVIDER_ORDER", f"{dropped},groq")
    assert dropped not in client_module.PROVIDERS
    assert [p.name for p in client_module.configured_providers()] == ["groq"]


def test_default_order_is_gemini_then_groq():
    assert client_module.DEFAULT_PROVIDER_ORDER == "gemini,groq"
    assert set(client_module.PROVIDERS) == {"gemini", "groq"}


def test_default_models_and_overrides(monkeypatch):
    _set_keys(monkeypatch, "gemini", "groq")
    models = {p.name: p.model for p in client_module.configured_providers()}
    assert models == {"gemini": "gemini-3.5-flash", "groq": "qwen/qwen3.8-27b"}

    monkeypatch.setenv("GEMINI_MODEL", "gemini-x")
    monkeypatch.setenv("GROQ_MODEL", "groq-y")
    models = {p.name: p.model for p in client_module.configured_providers()}
    assert models == {"gemini": "gemini-x", "groq": "groq-y"}


def test_placeholder_keys_count_as_missing(monkeypatch):
    _set_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    assert client_module.configured_providers() == []


def test_real_clients_use_provider_urls_and_no_sdk_retries(monkeypatch):
    _set_keys(monkeypatch, "gemini", "groq")
    clients = {p.name: p.client for p in client_module.configured_providers()}

    assert str(clients["gemini"].base_url).startswith("https://generativelanguage.googleapis.com/v1beta/openai")
    assert str(clients["groq"].base_url).startswith("https://api.groq.com/openai/v1")
    for client in clients.values():
        assert client.max_retries == 0  # the SDK must not retry underneath the failover policy
        assert client.timeout == client_module.LLM_REQUEST_TIMEOUT_SECONDS


def test_get_openai_client_returns_first_available(monkeypatch):
    _set_keys(monkeypatch, "groq", "gemini")
    assert str(client_module.get_openai_client().base_url).startswith("https://generativelanguage.googleapis.com")
    client_module.mark_exhausted("gemini", 60)
    assert str(client_module.get_openai_client().base_url).startswith("https://api.groq.com")


def test_get_openai_client_without_keys_raises(monkeypatch):
    _set_keys(monkeypatch)
    with pytest.raises(client_module.OpenAIClientError):
        client_module.get_openai_client()
