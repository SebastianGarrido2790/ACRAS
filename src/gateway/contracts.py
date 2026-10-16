"""Provider-neutral typed contracts, error taxonomy, and event models for LLM Gateway.

Governed by:
    INV-1 (ADR-001): Tiers 1-2 remain deterministic; gateway output never feeds
        deterministic calculations.
    INV-6 (ADR-006): All external LLM calls route through the gateway.
    ADR-009 / ADR-034: Custom gateway over Gemini primary and Groq-direct fallback.
    D3-01 / D3-04 / D3-05: Provider-neutral contracts, normalized error taxonomy,
        and structured sanitized event schemas.
    Phase 3 Feature SDD: 001_llm_gateway (GW-FR-01 to GW-FR-13).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GatewayMessageRole(StrEnum):
    """Permitted message roles for gateway requests."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class GatewayMessage(BaseModel):
    """Provider-neutral chat message contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: GatewayMessageRole = Field(description="Role of the message sender.")
    content: Annotated[str, Field(min_length=1, description="Message text payload.")]


class GatewayRequest(BaseModel):
    """Provider-neutral request contract for LLM invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    correlation_id: Annotated[
        str, Field(min_length=1, description="Unique correlation or tracking ID.")
    ]
    messages: Annotated[
        list[GatewayMessage],
        Field(min_length=1, description="Ordered sequence of conversation messages."),
    ]
    max_tokens: Annotated[
        int | None,
        Field(ge=1, le=8192, default=None, description="Upper bound on generation tokens."),
    ] = None
    temperature: Annotated[
        float,
        Field(
            ge=0.0,
            le=2.0,
            default=0.0,
            description="Sampling temperature (uniform low per INV-5).",
        ),
    ] = 0.0
    json_mode: Annotated[
        bool,
        Field(default=False, description="Flag requesting JSON object response envelope."),
    ] = False


class ProviderUsage(BaseModel):
    """Normalized token accounting reported by an inference provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_tokens: Annotated[int, Field(ge=0, description="Input/prompt token count.")]
    completion_tokens: Annotated[int, Field(ge=0, description="Generated output token count.")]
    total_tokens: Annotated[int, Field(ge=0, description="Total tokens consumed.")]
    details: dict[str, Any] | None = Field(
        default=None, description="Provider-specific granular timing/token details."
    )


class GatewayResult(BaseModel):
    """Normalized success outcome returned by the gateway."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    correlation_id: Annotated[str, Field(description="Originating request correlation ID.")]
    content: Annotated[str, Field(description="Generated text content from the provider.")]
    provider: Annotated[str, Field(description="Identifier of provider that produced the output.")]
    model: Annotated[str, Field(description="Exact model identifier that produced the output.")]
    fallback_used: Annotated[
        bool, Field(default=False, description="True if result was served by fallback provider.")
    ] = False
    finish_reason: str | None = Field(
        default=None, description="Completion stop condition (e.g. 'stop', 'length')."
    )
    latency_ms: Annotated[
        float, Field(ge=0.0, description="Total wall-clock duration of successful request in ms.")
    ]
    usage: ProviderUsage | None = Field(
        default=None,
        description="Provider-reported token usage; None if provider omitted usage metadata.",
    )
    cost_usd: float | None = Field(
        default=None,
        description="Computed cost in USD; None if usage or rate is unknown (never assumed 0.0).",
    )


class GatewayErrorCategory(StrEnum):
    """Bounded error taxonomy for normalizing gateway and provider failures."""

    CALLER_INPUT_ERROR = "caller_input_error"
    CONFIG_OR_AUTH_ERROR = "config_or_auth_error"
    TIMEOUT_ERROR = "timeout_error"
    CONNECTION_ERROR = "connection_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    DUAL_PROVIDER_FAILURE = "dual_provider_failure"
    UNKNOWN_PROVIDER_ERROR = "unknown_provider_error"


class GatewayError(Exception):
    """Normalized, sanitized exception raised when gateway operations fail."""

    def __init__(
        self,
        category: GatewayErrorCategory,
        message: str,
        *,
        correlation_id: str | None = None,
        provider: str | None = None,
        status_code: int | None = None,
        cause_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.correlation_id = correlation_id
        self.provider = provider
        self.status_code = status_code
        self.cause_error = cause_error

    def __str__(self) -> str:
        prov = f"[{self.provider}] " if self.provider else ""
        cid = f"(cid={self.correlation_id}) " if self.correlation_id else ""
        code = f"status={self.status_code} " if self.status_code else ""
        return f"{prov}{cid}{code}[{self.category.value}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Return a sanitized dictionary representation for event logging."""
        return {
            "category": self.category.value,
            "message": self.message,
            "correlation_id": self.correlation_id,
            "provider": self.provider,
            "status_code": self.status_code,
        }


class ProviderEvent(BaseModel):
    """Structured audit event emitted for every provider attempt and final outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 UTC timestamp of event generation.",
    )
    correlation_id: Annotated[str, Field(description="Request correlation identifier.")]
    event_type: Literal[
        "attempt", "success", "fallback", "breaker_transition", "failure"
    ] = Field(description="Category of lifecycle event.")
    provider: Annotated[str, Field(description="Target provider identifier.")]
    model: Annotated[str, Field(description="Exact model identifier.")]
    attempt: Annotated[
        int, Field(ge=1, le=2, description="Provider attempt sequence number (1 or 2).")
    ]
    outcome: Annotated[str, Field(description="Outcome status, e.g. 'success' or error category.")]
    latency_ms: float | None = Field(
        default=None, ge=0.0, description="Duration of this specific attempt in ms."
    )
    fallback_used: bool = Field(
        default=False, description="Flag indicating whether this attempt is the fallback path."
    )
    breaker_state: str | None = Field(
        default=None, description="Breaker state if transition occurred (closed, open, half_open)."
    )
    usage: ProviderUsage | None = Field(
        default=None, description="Usage metrics if available for this attempt."
    )
    cost_usd: float | None = Field(
        default=None, description="Estimated cost in USD if computable."
    )
    error_category: GatewayErrorCategory | None = Field(
        default=None, description="Normalized error category if attempt resulted in error."
    )
    error_message: str | None = Field(
        default=None, description="Sanitized error description; free of secrets or raw bodies."
    )
