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

__all__ = [
    "CostRateConfig",
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
    "calculate_cost_usd",
    "resolve_api_key",
]
