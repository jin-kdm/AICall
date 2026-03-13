"""Shared singleton OpenAI async client.

All services that call the OpenAI API should use `get_openai_client()`
instead of creating their own `AsyncOpenAI` instances.  This ensures a
single underlying httpx connection pool is reused, eliminating
per-request connection setup overhead.
"""

from openai import AsyncOpenAI

from backend.config import Settings

_client: AsyncOpenAI | None = None


def get_openai_client(settings: Settings) -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client
