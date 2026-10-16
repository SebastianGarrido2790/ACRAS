"""Versioned provider-event construction, redaction, and safe emission.

Governed by:
    D3-04 (Option B): Minimal structured event schema over standard-library
        logging; no observability platform in Phase 3.
    GW-FR-07 / GW-FR-08 / GW-FR-09 / GW-FR-10: Complete redacted events;
        unknown usage/cost stays unknown; never log prompts, completions,
        secrets, headers, or sensitive payloads.
    Stage 4: Allowlist field construction; emission failures never mask the
        gateway outcome.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.gateway.config import CostRateConfig, calculate_cost_usd
from src.gateway.contracts import (
    GatewayError,
    GatewayErrorCategory,
    GatewayResult,
    ProviderEvent,
)

EVENT_SCHEMA_VERSION = "v1"

_MAX_STRING_LENGTH = 500

_CREDENTIAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(api[_-]?key|apikey)\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bbearer\b\s+\S+"),
    re.compile(r"(?i)\b(token|secret|password|passwd|credential)\b\s*[:=]\s*\S+"),
    re.compile(r"\b(hf_[A-Za-z0-9]{10,}|gsk_[A-Za-z0-9]{10,}|sk-[A-Za-z0-9]{10,}|AIza[A-Za-z0-9_-]{10,})\b"),
)

_SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "prompt",
        "completion",
        "content",
        "messages",
        "raw_body",
        "raw_response",
        "authorization",
        "api_key",
        "apikey",
        "token",
        "secret",
        "password",
        "borrower",
        "ssn",
        "account_number",
    }
)


def redact_value(value: Any) -> Any:
    """Redact credential-like patterns and bound string lengths recursively."""
    if isinstance(value, str):
        scrubbed = value
        for pattern in _CREDENTIAL_PATTERNS:
            scrubbed = pattern.sub("[REDACTED]", scrubbed)
        if len(scrubbed) > _MAX_STRING_LENGTH:
            scrubbed = scrubbed[:_MAX_STRING_LENGTH] + "…[TRUNCATED]"
        return scrubbed
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_FIELD_NAMES:
                cleaned[str(key)] = "[REDACTED]"
            else:
                cleaned[str(key)] = redact_value(item)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [redact_value(item) for item in value]
    return value


def build_attempt_event(
    *,
    correlation_id: str,
    provider: str,
    model: str,
    attempt: int,
    fallback_used: bool = False,
) -> ProviderEvent:
    """Construct the attempt-started event (emitted before the provider call)."""
    return ProviderEvent(
        correlation_id=correlation_id,
        event_type="attempt",
        provider=provider,
        model=model,
        attempt=attempt,
        outcome="started",
        fallback_used=fallback_used,
    )


def build_result_event(
    result: GatewayResult,
    *,
    attempt: int,
    cost_rates: dict[str, CostRateConfig] | None = None,
) -> ProviderEvent:
    """Construct the success event from a normalized GatewayResult."""
    cost_usd: float | None = None
    if cost_rates is not None:
        cost_usd = calculate_cost_usd(result.model, result.usage, cost_rates)
    return ProviderEvent(
        correlation_id=result.correlation_id,
        event_type="fallback" if result.fallback_used else "success",
        provider=result.provider,
        model=result.model,
        attempt=attempt,
        outcome="success",
        latency_ms=result.latency_ms,
        fallback_used=result.fallback_used,
        usage=result.usage,
        cost_usd=cost_usd if cost_usd is not None else result.cost_usd,
    )


ERROR_DESCRIPTIONS: dict[GatewayErrorCategory, str] = {
    GatewayErrorCategory.CALLER_INPUT_ERROR: "Caller request failed input validation.",
    GatewayErrorCategory.CONFIG_OR_AUTH_ERROR: "Local configuration or credential fault.",
    GatewayErrorCategory.TIMEOUT_ERROR: "Provider request exceeded its bounded timeout.",
    GatewayErrorCategory.CONNECTION_ERROR: "Provider transport connection failed.",
    GatewayErrorCategory.RATE_LIMIT_ERROR: "Provider rate limit signaled; fallback eligible.",
    GatewayErrorCategory.PROVIDER_UNAVAILABLE: "Provider unavailable or server-side failure.",
    GatewayErrorCategory.INVALID_PROVIDER_RESPONSE: "Provider response failed validation.",
    GatewayErrorCategory.CIRCUIT_BREAKER_OPEN: "Provider circuit breaker open; not sent.",
    GatewayErrorCategory.DUAL_PROVIDER_FAILURE: "Primary and fallback attempts both failed.",
    GatewayErrorCategory.UNKNOWN_PROVIDER_ERROR: "Unclassified provider-side failure.",
}


def build_error_event(
    error: GatewayError,
    *,
    provider: str,
    model: str,
    attempt: int,
    latency_ms: float | None = None,
    fallback_used: bool = False,
    breaker_state: str | None = None,
) -> ProviderEvent:
    """Construct the failure event from a normalized GatewayError.

    The event's error message is a fixed per-category description, never the
    free-text exception message: arbitrary caller or provider content cannot
    reach logs through this path by construction.
    """
    return ProviderEvent(
        correlation_id=error.correlation_id or "unknown",
        event_type="failure",
        provider=provider,
        model=model,
        attempt=attempt,
        outcome=error.category.value,
        latency_ms=latency_ms,
        fallback_used=fallback_used,
        breaker_state=breaker_state,
        usage=None,
        cost_usd=None,
        error_category=error.category,
        error_message=ERROR_DESCRIPTIONS[error.category],
    )


def build_breaker_event(
    *,
    correlation_id: str,
    provider: str,
    model: str,
    breaker_state: str,
    previous_state: str | None = None,
) -> ProviderEvent:
    """Construct a breaker-transition event (attempt reflects the triggering call)."""
    if previous_state:
        outcome = f"breaker_{previous_state}_to_{breaker_state}"
    else:
        outcome = f"breaker_{breaker_state}"
    return ProviderEvent(
        correlation_id=correlation_id,
        event_type="breaker_transition",
        provider=provider,
        model=model,
        attempt=1,
        outcome=outcome,
        fallback_used=False,
        breaker_state=breaker_state,
    )


def serialize_event(event: ProviderEvent) -> str:
    """Serialize an event to a redacted single-line JSON record (schema v1)."""
    record = redact_value(event.model_dump(mode="json"))
    record["schema_version"] = EVENT_SCHEMA_VERSION
    return json.dumps(record, sort_keys=True)


def emit_event(logger: logging.Logger, event: ProviderEvent) -> bool:
    """Emit one event line; never raise (emission must not mask outcomes).

    The stdlib logging framework intentionally swallows handler-level faults,
    so this guard covers record construction and serialization failures —
    the failure classes this layer owns. A False return means the event was
    not emitted; the gateway outcome is unaffected either way.

    Returns:
        True if the record was handed to the logger, False otherwise.
    """
    try:
        line = serialize_event(event)
    except Exception:
        return False
    try:
        logger.info("%s", line)
        return True
    except Exception:
        return False
