"""LLM Gateway Module.

Custom pybreaker-backed circuit breaker and multi-provider routing interface
(Primary: Gemini, Fallback: Groq Cloud Direct).
"""

from src.gateway.config import (
    CostRateConfig,
    GatewayConfig,
    ProviderSettings,
    calculate_cost_usd,
    resolve_api_key,
)
from src.gateway.contracts import (
    GatewayError,
    GatewayErrorCategory,
    GatewayMessage,
    GatewayMessageRole,
    GatewayRequest,
    GatewayResult,
    ProviderEvent,
    ProviderUsage,
)
from src.gateway.events import (
    EVENT_SCHEMA_VERSION,
    build_attempt_event,
    build_breaker_event,
    build_error_event,
    build_result_event,
    emit_event,
    redact_value,
    serialize_event,
)

__all__ = [
    "CostRateConfig",
    "EVENT_SCHEMA_VERSION",
    "GatewayConfig",
    "GatewayError",
    "GatewayErrorCategory",
    "GatewayMessage",
    "GatewayMessageRole",
    "GatewayRequest",
    "GatewayResult",
    "ProviderEvent",
    "ProviderSettings",
    "ProviderUsage",
    "build_attempt_event",
    "build_breaker_event",
    "build_error_event",
    "build_result_event",
    "calculate_cost_usd",
    "emit_event",
    "redact_value",
    "resolve_api_key",
    "serialize_event",
]
