"""
OpenAI-Compatible Client Configuration Module

Every LLM call gets its provider(s) from here. All supported providers speak the
OpenAI chat-completions protocol, so the OpenAI Python SDK is used for all of
them.

Provider chain
--------------
The chain is a list of *entries* -- a provider plus one model -- tried in
``LLM_PROVIDER_ORDER`` (default ``gemini-lite,gemini-flash,groq``). Gemini's
free tier quotas are per model, so its two models are separate entries that
share ``GEMINI_API_KEY``: Flash-Lite (larger daily quota) first, then Flash.
``gemini`` in LLM_PROVIDER_ORDER is shorthand for both Gemini entries.

Entries whose API key is missing are skipped, so a deployment that only sets
``GROQ_API_KEY`` keeps working unchanged. Only providers with a free tier that
needs no payment method are supported (Mistral and Cerebras were dropped).

An entry that reports a *daily* quota exhaustion is parked for a cooldown
(``mark_exhausted``) so later requests go straight to the next entry instead
of paying a failed round trip every time. The failover policy itself lives in
``app.intent_extractor._create_completion_with_retry``.

Entries
-------
============  ==============  ==================  =====================  =================
entry         API key         model override      default model          free tier (owner)
============  ==============  ==================  =====================  =================
gemini-lite   GEMINI_API_KEY  GEMINI_LITE_MODEL   gemini-3.1-flash-lite  500 requests/day
gemini-flash  GEMINI_API_KEY  GEMINI_FLASH_MODEL  gemini-3.8-flash       20 requests/day
groq          GROQ_API_KEY    GROQ_MODEL          qwen/qwen3.8-27b       200K tokens/day
============  ==============  ==================  =====================  =================

Gemini model IDs were checked against the API's model list on 2026-10-02
(gemini-2.5-flash is listed but returns 404 "no longer available to new users").
"""

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class OpenAIClientError(Exception):
    """Custom exception for OpenAI-compatible client initialization errors."""
    pass


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    key_env: str
    model_env: str
    base_url: str
    default_model: str
    # How to force the single extraction tool. Gemini's OpenAI-compatible
    # layer only documents "auto", so the extractor also accepts a JSON reply
    # in the message content; Groq supports "required".
    tool_choice: str


_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

PROVIDERS: Dict[str, ProviderSpec] = {
    "gemini-lite": ProviderSpec(
        "gemini-lite", "GEMINI_API_KEY", "GEMINI_LITE_MODEL",
        _GEMINI_BASE_URL, "gemini-3.1-flash-lite", "auto",
    ),
    "gemini-flash": ProviderSpec(
        "gemini-flash", "GEMINI_API_KEY", "GEMINI_FLASH_MODEL",
        _GEMINI_BASE_URL, "gemini-3.8-flash", "auto",
    ),
    "groq": ProviderSpec(
        "groq", "GROQ_API_KEY", "GROQ_MODEL",
        "https://api.groq.com/openai/v1", "qwen/qwen3.8-27b", "required",
    ),
}

DEFAULT_PROVIDER_ORDER = "gemini-lite,gemini-flash,groq"
# Shorthands accepted in LLM_PROVIDER_ORDER.
_ALIASES = {"gemini": ["gemini-lite", "gemini-flash"]}
# A healthy extraction call takes a few seconds; gemini-lite occasionally hangs
# and, at 30 s, those requests took 35-40 s end to end (live, 2026-10-04).
DEFAULT_LLM_TIMEOUT_SECONDS = 12.0


def llm_timeout_seconds() -> float:
    """Per-request timeout (LLM_TIMEOUT_SECONDS); a hung provider fails over after this."""
    try:
        value = float(os.getenv("LLM_TIMEOUT_SECONDS", DEFAULT_LLM_TIMEOUT_SECONDS))
    except ValueError:
        return DEFAULT_LLM_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_LLM_TIMEOUT_SECONDS

_PLACEHOLDERS = {"your_groq_api_key_here", "your_gemini_api_key_here"}


@dataclass
class Provider:
    """A configured provider: spec + resolved model + (lazily built) client."""
    spec: ProviderSpec
    model: str
    api_key: str

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def tool_choice(self) -> str:
        return self.spec.tool_choice

    @property
    def client(self) -> OpenAI:
        with _lock:
            client = _clients.get(self.name)
            if client is None:
                # max_retries=0: the SDK would otherwise retry 429/5xx on its own
                # (2x, honoring Retry-After), hiding waits underneath the failover
                # policy. A bounded timeout lets a hung provider fail over.
                try:
                    client = OpenAI(
                        api_key=self.api_key,
                        base_url=self.spec.base_url,
                        max_retries=0,
                        timeout=llm_timeout_seconds(),
                    )
                except Exception as exc:
                    raise OpenAIClientError(f"Failed to initialize {self.name} client: {exc}")
                _clients[self.name] = client
            return client


_lock = threading.Lock()
_clients: Dict[str, OpenAI] = {}
_exhausted_until: Dict[str, float] = {}  # provider name -> time.monotonic() deadline


def provider_order() -> List[str]:
    """Chain entry names in the configured order (unknown names are ignored)."""
    raw = os.getenv("LLM_PROVIDER_ORDER", "").strip() or DEFAULT_PROVIDER_ORDER
    order = []
    for part in (part.strip().lower() for part in raw.split(",")):
        for name in _ALIASES.get(part, [part]):
            if not name or name in order:
                continue
            if name not in PROVIDERS:
                logger.warning("Ignoring unknown provider %r in LLM_PROVIDER_ORDER", name)
                continue
            order.append(name)
    return order


def configured_providers() -> List[Provider]:
    """Providers in order that have a real API key set."""
    providers = []
    for name in provider_order():
        spec = PROVIDERS[name]
        api_key = (os.getenv(spec.key_env) or "").strip()
        if not api_key or api_key in _PLACEHOLDERS:
            continue
        model = (os.getenv(spec.model_env) or "").strip() or spec.default_model
        providers.append(Provider(spec=spec, model=model, api_key=api_key))
    return providers


def available_providers(now: Optional[float] = None) -> List[Provider]:
    """Configured providers that are not parked after a daily-quota 429."""
    current = time.monotonic() if now is None else now
    with _lock:
        parked = {name for name, until in _exhausted_until.items() if until > current}
    return [p for p in configured_providers() if p.name not in parked]


def mark_exhausted(name: str, seconds: float, now: Optional[float] = None) -> None:
    """Park a provider (daily quota used up) for ``seconds``."""
    current = time.monotonic() if now is None else now
    with _lock:
        _exhausted_until[name] = current + max(seconds, 0.0)
    logger.warning("LLM provider %s parked for %.0fs (daily quota exhausted)", name, seconds)


def seconds_until_available(now: Optional[float] = None) -> Optional[float]:
    """Shortest remaining park time among configured providers, if all are parked."""
    current = time.monotonic() if now is None else now
    names = {p.name for p in configured_providers()}
    with _lock:
        remaining = [until - current for name, until in _exhausted_until.items()
                     if name in names and until > current]
    return min(remaining) if remaining else None


def get_openai_client() -> OpenAI:
    """
    Client for the first available provider in the chain.

    Kept for callers that only need "a" client; the extractor uses the whole
    chain via ``available_providers()``.

    Raises:
        OpenAIClientError: If no provider has an API key configured
    """
    providers = available_providers() or configured_providers()
    if not providers:
        raise OpenAIClientError(
            "API key not found. Set GEMINI_API_KEY and/or GROQ_API_KEY in your .env file."
        )
    return providers[0].client


def reset_client() -> None:
    """
    Reset cached clients and provider cooldowns.

    Useful for tests or when switching configuration at runtime.
    """
    with _lock:
        _clients.clear()
        _exhausted_until.clear()
