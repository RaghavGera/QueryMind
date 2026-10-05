"""
Multi-provider failover (app/openai_client.py + intent_extractor._create_completion_with_retry).

Chain entries: gemini-lite -> gemini-flash -> groq (both Gemini entries share
GEMINI_API_KEY). All providers are fakes; no network. Policy under test:
  * daily-quota 429 -> park the entry, fail over immediately, no retry
  * per-minute 429  -> at most one short retry (Retry-After honored), then fail over
  * 5xx / connection / other 4xx -> fail over
  * rate_limited is raised only when every configured entry is rate limited
"""

import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openai
import pytest

import app.intent_extractor as extractor
import app.openai_client as client_module
from app.intent_extractor import IntentExtractionError
from testing.llm_fakes import (
    FakeCompletions,
    Usage,
    auth_error,
    clear_provider_env,
    connection_error,
    daily_quota_error,
    http_response,
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


def gemini_daily_quota_error() -> openai.RateLimitError:
    """Shaped like Gemini's real free-tier 429 (captured 2026-10-02): a JSON list
    body, the per-day hint only in quotaId, and "retry in" instead of "try again in"."""
    body = [{"error": {
        "code": 429,
        "message": "You exceeded your current quota, please check your plan and billing details. "
                   "* Quota exceeded for metric: generativelanguage.googleapis.com/"
                   "generate_content_free_tier_requests, limit: 20, model: gemini-3.8-flash\n"
                   "Please retry in 10h5m39.009385224s.",
        "status": "RESOURCE_EXHAUSTED",
        "details": [{
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
        }],
    }}]
    return openai.RateLimitError(f"Error code: 429 - {json.dumps(body)}", response=http_response(429), body=body)


# ---------------------------------------------------------------------- #
# Required cases
# ---------------------------------------------------------------------- #

def test_provider_1_rate_limited_succeeds_on_provider_2(monkeypatch, sleeps, caplog):
    """(a) provider-1 429 -> answered by provider-2."""
    first = FakeCompletions(errors=[rate_limit_error(), rate_limit_error()])
    second = FakeCompletions(usage=Usage(prompt_tokens=321, completion_tokens=54))
    use_providers(monkeypatch, gemini_lite=first, groq=second)

    with caplog.at_level(logging.INFO, logger="app.intent_extractor"):
        intent = _ask()

    assert intent.tables == ["customers"]
    assert first.calls == 2   # call + one short retry, then fail over
    assert second.calls == 1
    assert len(sleeps) == 1
    served = [r.getMessage() for r in caplog.records if "LLM request served" in r.getMessage()]
    assert len(served) == 1
    assert re.fullmatch(
        r"LLM request served provider=groq model=groq-test-model prompt_tokens=321 completion_tokens=54 "
        r"seconds=\d+\.\d\d",
        served[0],
    )


def test_daily_quota_fails_over_immediately_without_retry(monkeypatch, sleeps):
    """(b) TPD-style 429 -> no retry loop, entry parked, straight to the next one."""
    first = FakeCompletions(errors=[daily_quota_error()])
    second = FakeCompletions()
    use_providers(monkeypatch, gemini_lite=first, groq=second)

    _ask()

    assert first.calls == 1
    assert second.calls == 1
    assert sleeps == []

    # Parked: the next request does not even try the exhausted entry.
    _ask()
    assert first.calls == 1
    assert second.calls == 2


# ---------------------------------------------------------------------- #
# The three-entry chain
# ---------------------------------------------------------------------- #

def test_lite_quota_exhausted_falls_to_flash_then_groq(monkeypatch, sleeps):
    lite = FakeCompletions(errors=[gemini_daily_quota_error()])
    flash = FakeCompletions(errors=[gemini_daily_quota_error()])
    groq = FakeCompletions()
    use_providers(monkeypatch, gemini_lite=lite, gemini_flash=flash, groq=groq)

    _ask()

    assert (lite.calls, flash.calls, groq.calls) == (1, 1, 1)
    assert sleeps == []
    assert lite.requests[0]["model"] == "gemini-lite-test-model"
    assert flash.requests[0]["model"] == "gemini-flash-test-model"


def test_gemini_quotas_are_tracked_per_model(monkeypatch, sleeps):
    # Lite's daily quota running out must not park Flash (quotas are per model).
    lite = FakeCompletions(errors=[gemini_daily_quota_error()])
    flash = FakeCompletions()
    use_providers(monkeypatch, gemini_lite=lite, gemini_flash=flash, groq=FakeCompletions())

    _ask()
    _ask()

    assert lite.calls == 1
    assert flash.calls == 2


def test_real_gemini_daily_quota_shape_is_recognised():
    error = gemini_daily_quota_error()
    assert extractor._is_daily_quota(error)
    assert extractor._daily_cooldown(error) == pytest.approx(10 * 3600 + 5 * 60 + 39.009385224)


# ---------------------------------------------------------------------- #
# Rest of the policy
# ---------------------------------------------------------------------- #

def test_daily_quota_cooldown_comes_from_the_providers_hint(monkeypatch, sleeps):
    use_providers(monkeypatch, groq=FakeCompletions(errors=[daily_quota_error("3m53.28s")]),
                  gemini_lite=FakeCompletions())
    _ask()
    remaining = client_module._exhausted_until["groq"] - client_module.time.monotonic()
    assert remaining == pytest.approx(233.28, abs=5)


def test_parked_entry_is_tried_again_after_its_cooldown(monkeypatch, sleeps):
    first = FakeCompletions(errors=[daily_quota_error("10s")])
    use_providers(monkeypatch, gemini_lite=first, groq=FakeCompletions())
    _ask()

    client_module._exhausted_until["gemini-lite"] = client_module.time.monotonic() - 1  # cooldown over
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
    "Quota exceeded for metric GenerateRequestsPerMinutePerProjectPerModel-FreeTier. Please retry in 23s.",
    "Requests rate limit exceeded",
])
def test_per_minute_limits_are_not_daily(message):
    assert not extractor._is_daily_quota(rate_limit_error(message=message))


def test_all_entries_rate_limited_raises_rate_limited(monkeypatch, sleeps):
    use_providers(
        monkeypatch,
        gemini_lite=FakeCompletions(errors=[gemini_daily_quota_error()]),
        gemini_flash=FakeCompletions(errors=[gemini_daily_quota_error()]),
        groq=FakeCompletions(errors=[rate_limit_error("2"), rate_limit_error("2")]),
    )

    with pytest.raises(IntentExtractionError) as excinfo:
        _ask()

    assert excinfo.value.kind == "rate_limited"
    assert excinfo.value.retry_after == 2


def test_when_every_entry_is_parked_no_call_is_made(monkeypatch, sleeps):
    first = FakeCompletions(errors=[daily_quota_error("10m")])
    second = FakeCompletions(errors=[daily_quota_error("4m")])
    use_providers(monkeypatch, gemini_lite=first, groq=second)
    with pytest.raises(IntentExtractionError):
        _ask()

    with pytest.raises(IntentExtractionError) as excinfo:
        _ask()

    assert excinfo.value.kind == "rate_limited"
    assert 200 < excinfo.value.retry_after <= 240  # the soonest entry comes back in ~4 minutes
    assert first.calls == 1 and second.calls == 1


def test_long_retry_after_fails_over_without_waiting(monkeypatch, sleeps):
    first = FakeCompletions(errors=[rate_limit_error(retry_after="45")])
    second = FakeCompletions()
    use_providers(monkeypatch, gemini_lite=first, groq=second)

    _ask()

    assert sleeps == []
    assert first.calls == 1 and second.calls == 1


def test_server_error_fails_over_without_retry(monkeypatch, sleeps):
    # e.g. gemini-3.8-flash answering 503 "high demand" (observed 2026-10-02)
    first = FakeCompletions(errors=[server_error()])
    second = FakeCompletions()
    use_providers(monkeypatch, gemini_flash=first, groq=second)

    _ask()

    assert first.calls == 1 and second.calls == 1 and sleeps == []


def test_misconfigured_provider_does_not_take_the_endpoint_down(monkeypatch, sleeps):
    # Gemini answers a bad key with HTTP 400 (observed); that must not break /query.
    bad_key = openai.BadRequestError("Please pass a valid API key", response=http_response(400), body=None)
    use_providers(monkeypatch, gemini_lite=FakeCompletions(errors=[bad_key]), groq=FakeCompletions())
    assert _ask().tables == ["customers"]


def test_mixed_failures_are_reported_as_unavailable(monkeypatch, sleeps):
    use_providers(
        monkeypatch,
        gemini_lite=FakeCompletions(errors=[daily_quota_error()]),
        groq=FakeCompletions(errors=[connection_error()]),
    )
    with pytest.raises(IntentExtractionError) as excinfo:
        _ask()
    assert excinfo.value.kind == "unavailable"


def test_only_bad_responses_are_reported_as_invalid(monkeypatch, sleeps):
    use_providers(monkeypatch, gemini_lite=FakeCompletions(errors=[auth_error()]),
                  groq=FakeCompletions(arguments="{nope"))
    with pytest.raises(IntentExtractionError) as excinfo:
        _ask()
    assert excinfo.value.kind == "invalid_response"


def test_unusable_answer_fails_over(monkeypatch, sleeps):
    first = FakeCompletions(content="Sure! Here are your customers.")  # no tool call, not JSON
    second = FakeCompletions()
    use_providers(monkeypatch, gemini_lite=first, groq=second)

    _ask()

    assert first.calls == 1 and second.calls == 1


def test_json_in_message_content_is_accepted(monkeypatch, sleeps):
    # Gemini runs with tool_choice="auto" and may answer in the message body.
    gemini = FakeCompletions(content='```json\n{"query_type": "select", "tables": ["customers"]}\n```')
    use_providers(monkeypatch, gemini_lite=gemini, groq=FakeCompletions())

    assert _ask().tables == ["customers"]
    assert gemini.calls == 1


def test_each_entry_gets_its_model_and_tool_choice(monkeypatch, sleeps):
    lite = FakeCompletions(errors=[server_error()])
    flash = FakeCompletions(errors=[server_error()])
    groq = FakeCompletions()
    use_providers(monkeypatch, gemini_lite=lite, gemini_flash=flash, groq=groq)

    _ask()

    assert (lite.requests[0]["model"], lite.requests[0]["tool_choice"]) == ("gemini-lite-test-model", "auto")
    assert (flash.requests[0]["model"], flash.requests[0]["tool_choice"]) == ("gemini-flash-test-model", "auto")
    assert (groq.requests[0]["model"], groq.requests[0]["tool_choice"]) == ("groq-test-model", "required")
    for completions in (lite, flash, groq):
        assert completions.requests[0]["max_tokens"] == 800
        assert "functions" not in completions.requests[0]


def test_no_provider_configured_is_a_clear_error(monkeypatch):
    use_providers(monkeypatch)  # none
    with pytest.raises(IntentExtractionError, match="API key not found"):
        _ask()


# ---------------------------------------------------------------------- #
# Configuration
# ---------------------------------------------------------------------- #

def _set_keys(monkeypatch, *key_envs):
    clear_provider_env(monkeypatch)
    for key_env in key_envs:
        monkeypatch.setenv(key_env, "k")


def _chain():
    return [(p.name, p.model) for p in client_module.configured_providers()]


def test_default_chain_is_fastest_first(monkeypatch):
    _set_keys(monkeypatch, "GEMINI_API_KEY", "GROQ_API_KEY")
    assert client_module.DEFAULT_PROVIDER_ORDER == "gemini-lite,groq,gemini-lite-alt,gemini-flash"
    assert _chain() == [
        ("gemini-lite", "gemini-3.5-flash-lite"),
        ("groq", "qwen/qwen3.8-27b"),
        ("gemini-lite-alt", "gemini-3.1-flash-lite"),
        ("gemini-flash", "gemini-3.8-flash"),
    ]


def test_one_gemini_key_enables_every_gemini_entry(monkeypatch):
    _set_keys(monkeypatch, "GEMINI_API_KEY")
    assert [name for name, _ in _chain()] == ["gemini-lite", "gemini-lite-alt", "gemini-flash"]


def test_groq_only_deployment_keeps_working(monkeypatch):
    _set_keys(monkeypatch, "GROQ_API_KEY")
    assert _chain() == [("groq", "qwen/qwen3.8-27b")]


def test_order_is_configurable_and_unknown_names_are_ignored(monkeypatch):
    _set_keys(monkeypatch, "GEMINI_API_KEY", "GROQ_API_KEY")
    monkeypatch.setenv("LLM_PROVIDER_ORDER", " groq, nonsense ,GEMINI-FLASH,groq")
    assert [name for name, _ in _chain()] == ["groq", "gemini-flash"]


def test_gemini_shorthand_expands_to_every_gemini_model_in_order(monkeypatch):
    _set_keys(monkeypatch, "GEMINI_API_KEY", "GROQ_API_KEY")
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "gemini,groq")
    assert [name for name, _ in _chain()] == ["gemini-lite", "gemini-lite-alt", "gemini-flash", "groq"]


@pytest.mark.parametrize("dropped", ["mistral", "cerebras", "openai"])
def test_dropped_providers_are_not_supported(monkeypatch, dropped):
    # Mistral and Cerebras need a payment method to activate.
    _set_keys(monkeypatch, "GROQ_API_KEY", f"{dropped.upper()}_API_KEY")
    monkeypatch.setenv("LLM_PROVIDER_ORDER", f"{dropped},groq")
    assert dropped not in client_module.PROVIDERS
    assert [name for name, _ in _chain()] == ["groq"]


def test_model_overrides(monkeypatch):
    _set_keys(monkeypatch, "GEMINI_API_KEY", "GROQ_API_KEY")
    monkeypatch.setenv("GEMINI_LITE_MODEL", "lite-x")
    monkeypatch.setenv("GEMINI_LITE_ALT_MODEL", "lite-w")
    monkeypatch.setenv("GEMINI_FLASH_MODEL", "flash-y")
    monkeypatch.setenv("GROQ_MODEL", "groq-z")
    assert _chain() == [
        ("gemini-lite", "lite-x"), ("groq", "groq-z"), ("gemini-lite-alt", "lite-w"), ("gemini-flash", "flash-y"),
    ]


def test_placeholder_keys_count_as_missing(monkeypatch):
    _set_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    assert client_module.configured_providers() == []


def test_real_clients_use_provider_urls_and_no_sdk_retries(monkeypatch):
    _set_keys(monkeypatch, "GEMINI_API_KEY", "GROQ_API_KEY")
    clients = {p.name: p.client for p in client_module.configured_providers()}

    for name in ("gemini-lite", "gemini-flash"):
        assert str(clients[name].base_url) == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert str(clients["groq"].base_url).startswith("https://api.groq.com/openai/v1")
    for client in clients.values():
        assert client.max_retries == 0  # the SDK must not retry underneath the failover policy
        assert client.timeout == client_module.DEFAULT_LLM_TIMEOUT_SECONDS


@pytest.mark.parametrize("raw, expected", [
    (None, 12.0), ("20", 20.0), ("7.5", 7.5), ("0", 12.0), ("-3", 12.0), ("soon", 12.0),
])
def test_llm_timeout_is_configurable(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    else:
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", raw)
    assert client_module.llm_timeout_seconds() == expected


def test_get_openai_client_returns_first_available(monkeypatch):
    _set_keys(monkeypatch, "GROQ_API_KEY", "GEMINI_API_KEY")
    assert str(client_module.get_openai_client().base_url).startswith("https://generativelanguage.googleapis.com")
    client_module.mark_exhausted("gemini-lite", 60)
    client_module.mark_exhausted("gemini-flash", 60)
    assert str(client_module.get_openai_client().base_url).startswith("https://api.groq.com")


def test_get_openai_client_without_keys_raises(monkeypatch):
    _set_keys(monkeypatch)
    with pytest.raises(client_module.OpenAIClientError):
        client_module.get_openai_client()
