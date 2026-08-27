"""
OpenAI-Compatible Client Configuration Module

This module provides a centralized client instance for OpenAI-compatible APIs.
It supports both Groq and OpenAI APIs, with automatic detection based on which
API key is present in the environment. The client uses the OpenAI Python library
which is compatible with Groq's API.
"""

import os
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class OpenAIClientError(Exception):
    """Custom exception for OpenAI-compatible client initialization errors."""
    pass


_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """
    Get or create a configured OpenAI-compatible client instance.

    This function implements a singleton pattern to ensure only one client
    instance is created throughout the application lifecycle. It supports both
    Groq and OpenAI APIs, checking for GROQ_API_KEY first, then falling back
    to OPENAI_API_KEY.

    Returns:
        OpenAI: Configured OpenAI-compatible client instance (Groq or OpenAI)

    Raises:
        OpenAIClientError: If the API key is not configured or invalid

    Example:
        >>> client = get_openai_client()
        >>> response = client.chat.completions.create(...)
    """
    global _client

    if _client is not None:
        return _client

    # Check for Groq API key first, then fall back to OpenAI
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    use_groq = bool(os.getenv("GROQ_API_KEY"))

    if not api_key:
        raise OpenAIClientError(
            "API key not found. Please set either GROQ_API_KEY or OPENAI_API_KEY in your .env file."
        )

    if api_key == "your_openai_api_key_here" or api_key == "your_groq_api_key_here":
        raise OpenAIClientError(
            "API key is not configured. Please replace the placeholder "
            "with your actual API key in the .env file."
        )

    try:
        if use_groq:
            # Configure for Groq API (OpenAI-compatible)
            _client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )
        else:
            # Configure for OpenAI API
            _client = OpenAI(api_key=api_key)
        return _client
    except Exception as e:
        provider = "Groq" if use_groq else "OpenAI"
        raise OpenAIClientError(f"Failed to initialize {provider} client: {str(e)}")


def reset_client() -> None:
    """
    Reset the client instance.

    This is useful for testing or when you need to reinitialize
    the client with different configuration (e.g., switching between
    Groq and OpenAI).
    """
    global _client
    _client = None
