"""Provider adapters for the LLM gateway (D3-01 Option B).

Thin per-provider modules over one shared injectable transport. No adapter
performs retries; attempt policy belongs to the gateway orchestration layer.
"""

from src.gateway.providers.base import (
    AdapterContext,
    build_headers,
    normalize_error,
    post_chat_completion,
)
from src.gateway.providers.gemini import invoke_gemini
from src.gateway.providers.groq import invoke_groq

__all__ = [
    "AdapterContext",
    "build_headers",
    "invoke_gemini",
    "invoke_groq",
    "normalize_error",
    "post_chat_completion",
]
