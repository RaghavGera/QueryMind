"""LLM provider selection: Groq stays the default; others are opt-in."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import app.openai_client as client_module
from app.openai_client import OpenAIClientError, get_model, get_provider

KEYS = ["LLM_PROVIDER", "QUERYMIND_LLM_MODEL", "GROQ_API_KEY", "MISTRAL_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    client_module.reset_client()
    yield
    client_module.reset_client()


def test_existing_groq_deployments_need_no_new_settings(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    assert get_provider().name == "groq"
    assert get_model() == "qwen/qwen3.8-27b"


def test_provider_is_inferred_from_the_key_present(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    assert get_provider().name == "mistral"
    assert get_model() == "mistral-small-latest"


def test_explicit_provider_wins_over_inference(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    monkeypatch.setenv("LLM_PROVIDER", "mistral")
    assert get_provider().name == "mistral"


def test_model_override(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("QUERYMIND_LLM_MODEL", "some-model")
    assert get_model() == "some-model"


def test_gemini_requires_an_explicit_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    with pytest.raises(OpenAIClientError, match="QUERYMIND_LLM_MODEL"):
        get_model()
    monkeypatch.setenv("QUERYMIND_LLM_MODEL", "x")
    assert get_model() == "x"


def test_unknown_provider_and_missing_key_are_clear_errors(monkeypatch):
    with pytest.raises(OpenAIClientError, match="API key not found"):
        get_provider()
    monkeypatch.setenv("LLM_PROVIDER", "nope")
    with pytest.raises(OpenAIClientError, match="Unknown LLM_PROVIDER"):
        get_provider()


def test_client_uses_the_providers_base_url(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mistral")
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    assert str(client_module.get_openai_client().base_url).startswith("https://api.mistral.ai/v1")


def test_provider_without_its_key_fails_clearly(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mistral")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    with pytest.raises(OpenAIClientError, match="MISTRAL_API_KEY"):
        client_module.get_openai_client()
