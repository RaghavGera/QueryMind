"""
Test doubles for the LLM provider chain (no network).

``use_providers(monkeypatch, gemini=FakeCompletions(...), groq=...)`` configures
exactly those providers (in that order) with fake API keys and installs fake
clients in ``app.openai_client``'s client cache, so tests exercise the real
chain/failover code end to end.
"""

import json

import httpx
import openai

import app.openai_client as client_module

ALL_KEY_ENVS = [spec.key_env for spec in client_module.PROVIDERS.values()]
ALL_MODEL_ENVS = [spec.model_env for spec in client_module.PROVIDERS.values()]

DEFAULT_ARGUMENTS = '{"query_type": "select", "tables": ["customers"]}'


def http_response(status: int, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, headers=headers or {}, request=httpx.Request("POST", "https://llm.test/v1/chat"))


def rate_limit_error(retry_after: str | None = None, message: str = "rate limited") -> openai.RateLimitError:
    headers = {"retry-after": retry_after} if retry_after else {}
    return openai.RateLimitError(message, response=http_response(429, headers), body=None)


def daily_quota_error(wait: str = "3m53.28s") -> openai.RateLimitError:
    """Shaped like Groq's real TPD 429 (captured 2026-10-02)."""
    message = (
        "Error code: 429 - Rate limit reached for model `qwen/qwen3.8-27b` in organization `org_x` "
        "service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199627, Requested 913. "
        f"Please try again in {wait}."
    )
    return openai.RateLimitError(message, response=http_response(429, {"retry-after": "234"}), body=None)


def server_error() -> openai.InternalServerError:
    return openai.InternalServerError("upstream down", response=http_response(503), body=None)


def auth_error() -> openai.AuthenticationError:
    return openai.AuthenticationError("invalid api key", response=http_response(401), body=None)


def connection_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(request=httpx.Request("POST", "https://llm.test/v1/chat"))


class Usage:
    def __init__(self, prompt_tokens=123, completion_tokens=45):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class FakeCompletions:
    """
    Raises the queued errors in order, then answers with a tool call carrying
    ``arguments`` (or plain ``content`` when ``content`` is given).
    Records every request's kwargs in ``requests``.
    """

    def __init__(self, errors=(), arguments=DEFAULT_ARGUMENTS, content=None, usage=None):
        self.errors = list(errors)
        self.arguments = arguments if isinstance(arguments, str) else json.dumps(arguments)
        self.content = content
        self.usage = usage or Usage()
        self.requests = []

    @property
    def calls(self) -> int:
        return len(self.requests)

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.errors:
            raise self.errors.pop(0)
        if self.content is not None:
            message = type("M", (), {"tool_calls": None, "content": self.content})()
        else:
            call = type("TC", (), {"function": type("F", (), {"arguments": self.arguments})()})()
            message = type("M", (), {"tool_calls": [call], "content": None})()
        return type("R", (), {"choices": [type("C", (), {"message": message})()], "usage": self.usage})()


class FakeClient:
    def __init__(self, completions: FakeCompletions):
        self.chat = type("Chat", (), {"completions": completions})()


def clear_provider_env(monkeypatch) -> None:
    for name in ALL_KEY_ENVS + ALL_MODEL_ENVS + ["LLM_PROVIDER_ORDER"]:
        monkeypatch.delenv(name, raising=False)
    client_module.reset_client()


def use_providers(monkeypatch, **completions_by_provider: FakeCompletions) -> None:
    """Configure exactly these providers, in keyword order, backed by fakes."""
    clear_provider_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER_ORDER", ",".join(completions_by_provider))
    for name, completions in completions_by_provider.items():
        spec = client_module.PROVIDERS[name]
        monkeypatch.setenv(spec.key_env, f"test-key-{name}")
        monkeypatch.setenv(spec.model_env, f"{name}-test-model")
        client_module._clients[name] = FakeClient(completions)
