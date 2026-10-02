"""
OpenAI-Compatible Client Configuration Module

One place for every LLM call to get its client, model and provider settings.
All supported providers speak the OpenAI chat-completions protocol, so the
OpenAI Python SDK is used for all of them.

Provider selection
------------------
``LLM_PROVIDER`` = ``groq`` | ``mistral`` | ``gemini`` | ``openai``.
If unset, the provider is inferred from whichever API key is present
(GROQ_API_KEY, then MISTRAL_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY), so an
existing Groq deployment keeps working with no changes.

``QUERYMIND_LLM_MODEL`` overrides the provider's default model.
"""

import os
from dataclasses import dataclass
from typing import Dict, Optional

from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class OpenAIClientError(Exception):
    """Custom exception for OpenAI-compatible client initialization errors."""
    pass


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    key_env: str
    base_url: Optional[str]
    default_model: Optional[str]


PROVIDERS: Dict[str, ProviderSpec] = {
    "groq": ProviderSpec("groq", "GROQ_API_KEY", "https://api.groq.com/openai/v1", "qwen/qwen3.8-27b"),
    "mistral": ProviderSpec("mistral", "MISTRAL_API_KEY", "https://api.mistral.ai/v1", "mistral-small-latest"),
    # No default model: Google renames Gemini models often, so set QUERYMIND_LLM_MODEL.
    "gemini": ProviderSpec(
        "gemini", "GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai/", None
    ),
    "openai": ProviderSpec("openai", "OPENAI_API_KEY", None, "gpt-4o-mini"),
}

_PLACEHOLDERS = {"your_openai_api_key_here", "your_groq_api_key_here"}

_client: Optional[OpenAI] = None


def get_provider() -> ProviderSpec:
    """Resolve the configured provider (explicit LLM_PROVIDER, else by API key)."""
    chosen = os.getenv("LLM_PROVIDER", "").strip().lower()
    if chosen:
        if chosen not in PROVIDERS:
            raise OpenAIClientError(
                f"Unknown LLM_PROVIDER '{chosen}'. Choose one of: {', '.join(PROVIDERS)}."
            )
        return PROVIDERS[chosen]
    for spec in PROVIDERS.values():
        if os.getenv(spec.key_env):
            return spec
    raise OpenAIClientError(
        "API key not found. Set LLM_PROVIDER and the matching key "
        "(GROQ_API_KEY, MISTRAL_API_KEY, GEMINI_API_KEY or OPENAI_API_KEY)."
    )


def get_model() -> str:
    """Model id: QUERYMIND_LLM_MODEL if set, else the provider default."""
    override = os.getenv("QUERYMIND_LLM_MODEL", "").strip()
    if override:
        return override
    spec = get_provider()
    if spec.default_model is None:
        raise OpenAIClientError(
            f"No default model for {spec.name}. Set QUERYMIND_LLM_MODEL to the model id to use."
        )
    return spec.default_model


def get_openai_client() -> OpenAI:
    """
    Get or create the configured OpenAI-compatible client (singleton).

    Raises:
        OpenAIClientError: If the provider/API key is missing or invalid
    """
    global _client

    if _client is not None:
        return _client

    spec = get_provider()
    api_key = os.getenv(spec.key_env)

    if not api_key:
        raise OpenAIClientError(f"{spec.key_env} is not set (provider: {spec.name}).")

    if api_key in _PLACEHOLDERS:
        raise OpenAIClientError(
            "API key is not configured. Please replace the placeholder "
            "with your actual API key in the .env file."
        )

    try:
        if spec.base_url:
            _client = OpenAI(api_key=api_key, base_url=spec.base_url)
        else:
            _client = OpenAI(api_key=api_key)
        return _client
    except Exception as e:
        raise OpenAIClientError(f"Failed to initialize {spec.name} client: {str(e)}")


def reset_client() -> None:
    """
    Reset the client instance.

    Useful for tests or when switching provider/configuration at runtime.
    """
    global _client
    _client = None
