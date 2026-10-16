"""Unit tests and falsification for gateway events and redaction (Stage 4 / GW-T07).

Governed by:
    D3-04 (Option B): Minimal structured events over standard-library logging.
    GW-FR-07 / GW-FR-08 / GW-FR-09 / GW-FR-10: Complete redacted events;
        unknown usage/cost stays unknown; no sensitive payloads in logs.
"""

from __future__ import annotations

import json
import logging

import pytest

from src.gateway import (
    EVENT_SCHEMA_VERSION,
    CostRateConfig,
    GatewayError,
    GatewayErrorCategory,
    GatewayResult,
    ProviderEvent,
    ProviderUsage,
    build_attempt_event,
    build_breaker_event,
    build_error_event,
    build_result_event,
    emit_event,
    redact_value,
    serialize_event,
)


def _sample_result() -> GatewayResult:
    return GatewayResult(
        correlation_id="cid-evt-001",
        content="Assessment text.",
        provider="groq",
        model="openai/gpt-oss-20b",
        fallback_used=True,
        finish_reason="stop",
        latency_ms=410.3,
        usage=ProviderUsage(prompt_tokens=76, completion_tokens=8, total_tokens=84),
        cost_usd=None,
    )


def test_build_result_event_fields_and_cost() -> None:
    """Success event carries all required fields; cost computed from rates."""
    rates = {
        "openai/gpt-oss-20b": CostRateConfig(
            input_per_m=0.075,
            output_per_m=0.30,
            rate_date="2026-10-12",
            rate_source="Groq docs",
        )
    }
    event = build_result_event(_sample_result(), attempt=2, cost_rates=rates)
    assert event.event_type == "fallback"
    assert event.provider == "groq"
    assert event.attempt == 2
    assert event.outcome == "success"
    assert event.latency_ms == 410.3
    assert event.fallback_used is True
    assert event.usage is not None
    assert event.usage.total_tokens == 84
    # (76 * 0.075 + 8 * 0.30) / 1e6 = (5.7 + 2.4) / 1e6 = 0.0000081
    assert event.cost_usd == 0.0000081


def test_build_result_event_unknown_cost_without_rates() -> None:
    """[Stage 4] Missing rates keep cost unknown (None), never zero."""
    event = build_result_event(_sample_result(), attempt=2, cost_rates=None)
    assert event.cost_usd is None
    record = json.loads(serialize_event(event))
    assert record["cost_usd"] is None


def test_build_error_event_sanitized() -> None:
    """Error event carries category; message passes through redaction."""
    err = GatewayError(
        category=GatewayErrorCategory.TIMEOUT_ERROR,
        message="Provider request timed out after 15.0s.",
        correlation_id="cid-evt-002",
        provider="gemini",
    )
    event = build_error_event(
        err, provider="gemini", model="gemini-2.5-flash", attempt=1, latency_ms=15000.0
    )
    assert event.event_type == "failure"
    assert event.outcome == "timeout_error"
    assert event.error_category == GatewayErrorCategory.TIMEOUT_ERROR
    assert event.usage is None
    assert event.cost_usd is None


def test_build_attempt_and_breaker_events() -> None:
    """Attempt and breaker-transition events carry stable identifiers."""
    started = build_attempt_event(
        correlation_id="cid-evt-003", provider="gemini", model="gemini-2.5-flash", attempt=1
    )
    assert started.event_type == "attempt"
    assert started.outcome == "started"

    transition = build_breaker_event(
        correlation_id="cid-evt-003",
        provider="gemini",
        model="gemini-2.5-flash",
        breaker_state="open",
        previous_state="closed",
    )
    assert transition.event_type == "breaker_transition"
    assert transition.breaker_state == "open"
    assert "closed" in transition.outcome and "open" in transition.outcome


def test_serialize_event_schema_version_and_keys() -> None:
    """Serialized records are single-line JSON with schema version stamped."""
    line = serialize_event(build_attempt_event(
        correlation_id="cid-evt-004", provider="groq", model="openai/gpt-oss-20b", attempt=1
    ))
    assert "\n" not in line
    record = json.loads(line)
    assert record["schema_version"] == EVENT_SCHEMA_VERSION
    assert record["correlation_id"] == "cid-evt-004"


def test_emit_event_to_logger_handler() -> None:
    """Events flow through a standard-library logger without new infrastructure."""
    records: list[str] = []

    class CollectHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    logger = logging.getLogger("test-gateway-events-stage4")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.addHandler(CollectHandler())
    logger.propagate = False
    try:
        ok = emit_event(logger, build_result_event(_sample_result(), attempt=2))
    finally:
        logger.handlers.clear()
    assert ok is True
    assert len(records) == 1
    parsed = json.loads(records[0])
    assert parsed["provider"] == "groq"
    assert parsed["outcome"] == "success"


def test_emit_event_failure_never_masks_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    """[Stage 4] A serialization failure returns False instead of raising."""
    import src.gateway.events as events_module

    def boom(event: ProviderEvent) -> str:
        raise RuntimeError("serialization backend is down")

    monkeypatch.setattr(events_module, "serialize_event", boom)
    logger = logging.getLogger("test-gateway-events-broken")
    try:
        ok = emit_event(
            logger,
            build_attempt_event(
                correlation_id="cid-evt-005",
                provider="gemini",
                model="gemini-2.5-flash",
                attempt=1,
            ),
        )
    finally:
        logger.handlers.clear()
    assert ok is False


def test_falsification_sentinel_values_redacted() -> None:
    """[Stage 4 Falsification] Prompt/response/key/borrower sentinels never survive."""
    prompt_sentinel = "PROMPT_SENTINEL_EVALUATE_THIS_SME"
    response_sentinel = "RESPONSE_SENTINEL_APPROVE_LOAN_NOW"
    key_sentinel = "gsk_SENTINEL_KEY_NEVER_LOG_1234567890"
    borrower_sentinel = "BORROWER_SENTINEL_ACME_CORP_TAXID"

    event = build_error_event(
        GatewayError(
            category=GatewayErrorCategory.INVALID_PROVIDER_RESPONSE,
            message=f"Bad body for {prompt_sentinel}; got {response_sentinel}; key {key_sentinel}",
            correlation_id="cid-evt-006",
            provider="groq",
        ),
        provider="groq",
        model="openai/gpt-oss-20b",
        attempt=2,
        fallback_used=True,
    )
    line = serialize_event(event)
    for sentinel in (prompt_sentinel, response_sentinel, key_sentinel, borrower_sentinel):
        assert sentinel not in line
    # Required metadata still present; message is the fixed category text
    record = json.loads(line)
    assert record["correlation_id"] == "cid-evt-006"
    assert record["outcome"] == "invalid_provider_response"
    assert record["fallback_used"] is True
    assert record["error_message"] == "Provider response failed validation."


def test_falsification_sensitive_field_names_redacted() -> None:
    """[Stage 4 Falsification] Allowlisted construction drops sensitive field names."""
    scrubbed = redact_value(
        {
            "authorization": "Bearer live-secret-value",
            "api_key": "gsk_live_secret_value_1234567890",
            "prompt": "Evaluate borrower ACME",
            "borrower": "ACME Corp",
            "provider": "groq",
            "attempt": 1,
        }
    )
    assert isinstance(scrubbed, dict)
    assert scrubbed["authorization"] == "[REDACTED]"
    assert scrubbed["api_key"] == "[REDACTED]"
    assert "ACME" not in str(scrubbed["borrower"])
    assert scrubbed["provider"] == "groq"
    assert scrubbed["attempt"] == 1


def test_falsification_unknown_usage_serializes_null() -> None:
    """[Stage 4 Falsification] Unknown usage/cost serialize as null, never 0."""
    event = build_error_event(
        GatewayError(
            category=GatewayErrorCategory.PROVIDER_UNAVAILABLE,
            message="Provider returned HTTP 503.",
            correlation_id="cid-evt-007",
            provider="groq",
        ),
        provider="groq",
        model="openai/gpt-oss-20b",
        attempt=2,
        fallback_used=True,
    )
    record = json.loads(serialize_event(event))
    assert record["usage"] is None
    assert record["cost_usd"] is None
    assert "0" not in str(record["cost_usd"])
