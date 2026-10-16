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

__all__ = [
    "AdapterContext",
    "build_headers",
    "normalize_error",
    "post_chat_completion",
]
