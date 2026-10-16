"""Unit tests and falsification checks for LLM Gateway contracts and configuration.

Governed by:
    INV-1 (ADR-001): Gateway outputs remain separate from deterministic tiers.
    INV-6 (ADR-006): Gateway contract enforces bounded, typed interaction.
    ADR-009 / ADR-034: Gemini primary and Groq-direct fallback configuration.
    D3-01 / D3-03 / D3-04 / D3-05: Gateway contracts, resilience settings,
        cost accounting, and error taxonomy.
    Phase 3 Feature SDD: 001_llm_gateway (GW-FR-01 to GW-FR-13).
"""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from src.config.loader import load_params
from src.gateway import (
    CostRateConfig,
    GatewayConfig,
    GatewayError,
    GatewayErrorCategory,
    GatewayMessage,
    GatewayMessageRole,
    GatewayRequest,
    GatewayResult,
    ProviderEvent,
    ProviderSettings,
    ProviderUsage,
    calculate_cost_usd,
    resolve_api_key,
)
from src.schemas import EvidenceBundle, PDBand


def test_gateway_message_roles_and_validation() -> None:
    """Verify GatewayMessage accepts valid roles and rejects invalid inputs."""
    msg = GatewayMessage(role=GatewayMessageRole.USER, content="Hello")
    assert msg.role == GatewayMessageRole.USER
    assert msg.content == "Hello"

    # String literal conversion works
    msg2 = GatewayMessage(role="system", content="System instruction")  # type: ignore[arg-type]
    assert msg2.role == GatewayMessageRole.SYSTEM

    # Empty content rejected
    with pytest.raises(ValidationError):
        GatewayMessage(role=GatewayMessageRole.USER, content="")

    # Invalid role rejected
    with pytest.raises(ValidationError):
        GatewayMessage(role="invalid_role", content="text")  # type: ignore[arg-type]

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        GatewayMessage(
            role=GatewayMessageRole.USER,
            content="text",
            extra_field="rejected",  # type: ignore[call-arg]
        )


def test_gateway_request_bounds_and_defaults() -> None:
    """Verify GatewayRequest defaults, field bounds, and rejection of invalid values."""
    req = GatewayRequest(
        correlation_id="req-001",
        messages=[GatewayMessage(role=GatewayMessageRole.USER, content="Evaluate SME risk")],
    )
    assert req.correlation_id == "req-001"
    assert req.temperature == 0.0
    assert req.max_tokens is None
    assert req.json_mode is False

    # Temperature out of bounds (> 2.0 or < 0.0)
    with pytest.raises(ValidationError):
        GatewayRequest(
            correlation_id="req-002",
            messages=[GatewayMessage(role=GatewayMessageRole.USER, content="Hi")],
            temperature=2.5,
        )

    with pytest.raises(ValidationError):
        GatewayRequest(
            correlation_id="req-002",
            messages=[GatewayMessage(role=GatewayMessageRole.USER, content="Hi")],
            temperature=-0.1,
        )

    # max_tokens out of bounds (< 1 or > 8192)
    with pytest.raises(ValidationError):
        GatewayRequest(
            correlation_id="req-003",
            messages=[GatewayMessage(role=GatewayMessageRole.USER, content="Hi")],
            max_tokens=0,
        )

    with pytest.raises(ValidationError):
        GatewayRequest(
            correlation_id="req-003",
            messages=[GatewayMessage(role=GatewayMessageRole.USER, content="Hi")],
            max_tokens=100_000,
        )

    # Empty messages list rejected
    with pytest.raises(ValidationError):
        GatewayRequest(correlation_id="req-004", messages=[])

    # Empty correlation_id rejected
    with pytest.raises(ValidationError):
        GatewayRequest(
            correlation_id="",
            messages=[GatewayMessage(role=GatewayMessageRole.USER, content="Hi")],
        )


def test_provider_usage_and_gateway_result_contracts() -> None:
    """Verify ProviderUsage and GatewayResult normalized schemas."""
    usage = ProviderUsage(
        prompt_tokens=45,
        completion_tokens=12,
        total_tokens=57,
        details={"queue_time_ms": 15.2},
    )
    assert usage.prompt_tokens == 45
    assert usage.total_tokens == 57
    assert usage.details == {"queue_time_ms": 15.2}

    # Negative tokens rejected
    with pytest.raises(ValidationError):
        ProviderUsage(prompt_tokens=-1, completion_tokens=10, total_tokens=9)

    res = GatewayResult(
        correlation_id="corr-101",
        content='{"verdict": "approve"}',
        provider="gemini",
        model="gemini-2.5-flash",
        fallback_used=False,
        finish_reason="stop",
        latency_ms=420.5,
        usage=usage,
        cost_usd=0.00001,
    )
    assert res.provider == "gemini"
    assert res.fallback_used is False
    assert res.latency_ms == 420.5
    assert res.cost_usd == 0.00001


def test_gateway_error_taxonomy_and_sanitization() -> None:
    """Verify GatewayError category categorization and sanitized representation."""
    err = GatewayError(
        category=GatewayErrorCategory.TIMEOUT_ERROR,
        message="Request timed out after 15.0s",
        correlation_id="corr-err-1",
        provider="gemini",
        status_code=504,
    )
    assert err.category == GatewayErrorCategory.TIMEOUT_ERROR
    assert err.status_code == 504
    assert "[gemini]" in str(err)
    assert "timeout_error" in str(err)

    data = err.to_dict()
    assert data["category"] == "timeout_error"
    assert data["provider"] == "gemini"


def test_provider_event_model() -> None:
    """Verify ProviderEvent structured audit record schema."""
    event = ProviderEvent(
        correlation_id="cid-999",
        event_type="attempt",
        provider="groq",
        model="openai/gpt-oss-20b",
        attempt=1,
        outcome="success",
        latency_ms=350.2,
        fallback_used=True,
        breaker_state="closed",
    )
    assert event.event_type == "attempt"
    assert event.fallback_used is True
    assert event.attempt == 1

    # Attempt out of bounds (> 2 or < 1)
    with pytest.raises(ValidationError):
        ProviderEvent(
            correlation_id="cid-999",
            event_type="attempt",
            provider="groq",
            model="openai/gpt-oss-20b",
            attempt=3,
            outcome="failure",
        )


def test_gateway_configuration_from_params_yaml() -> None:
    """Verify GatewayConfig loads cleanly from params.yaml with approved values."""
    params = load_params("params.yaml")
    assert params.gateway is not None
    gw = params.gateway

    assert gw.primary.provider == "gemini"
    assert gw.primary.model == "gemini-2.5-flash"
    assert gw.primary.timeout_s == 15.0
    assert "generativelanguage.googleapis.com" in gw.primary.base_url

    assert gw.fallback.provider == "groq"
    assert gw.fallback.model == "openai/gpt-oss-20b"
    assert gw.fallback.timeout_s == 20.0
    assert "api.groq.com" in gw.fallback.base_url

    assert gw.max_attempts == 2
    assert gw.retries_per_provider == 0
    assert gw.breaker_failure_threshold == 3
    assert gw.breaker_recovery_timeout_s == 30.0
    assert gw.breaker_half_open_probes == 1
    assert "Mozilla" in gw.default_user_agent

    # Cost rates present for both models
    assert "gemini-2.5-flash" in gw.cost_rates
    assert "openai/gpt-oss-20b" in gw.cost_rates


def test_calculate_cost_usd_accuracy_and_unknown_handling() -> None:
    """Verify cost calculation follows GW-FR-09 and D3-04 (unknown stays unknown)."""
    rates = {
        "test-model": CostRateConfig(
            input_per_m=2.0,
            output_per_m=10.0,
            rate_date="2026-10-12",
            rate_source="Test Pricing",
        )
    }

    # 1. Unknown usage returns None (never assumed 0.0)
    assert calculate_cost_usd("test-model", None, rates) is None

    # 2. Unknown model returns None
    usage = ProviderUsage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
    assert calculate_cost_usd("unregistered-model", usage, rates) is None

    # 3. Valid calculation: (1000 * 2.0 + 500 * 10.0) / 1,000,000 = (2000 + 5000) / 1M = 0.007 USD
    cost = calculate_cost_usd("test-model", usage, rates)
    assert cost == pytest.approx(0.007)


def test_resolve_api_key_safe_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify out-of-band secret resolution and safe missing-key errors."""
    # 1. Missing key raises GatewayError(CONFIG_OR_AUTH_ERROR)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(GatewayError) as exc_info:
        resolve_api_key("gemini")
    assert exc_info.value.category == GatewayErrorCategory.CONFIG_OR_AUTH_ERROR
    assert "GEMINI_API_KEY" in str(exc_info.value)

    # 2. Present key returns trimmed secret
    monkeypatch.setenv("GEMINI_API_KEY", "  test-gemini-secret-key  ")
    resolved = resolve_api_key("gemini")
    assert resolved == "test-gemini-secret-key"

    # 3. Groq key resolution
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_groq_key")
    assert resolve_api_key("groq") == "gsk_test_groq_key"


# ---------------------------------------------------------------------------
# Stage 1 Falsifications (Gate 1 Requirements)
# ---------------------------------------------------------------------------


def test_falsification_out_of_range_timeouts_and_thresholds() -> None:
    """[Gate 1 Falsification] Out-of-bounds timeouts and thresholds raise ValidationError."""
    primary = ProviderSettings(
        provider="gemini",
        model="gemini-2.5-flash",
        base_url="https://api.example.com",
        timeout_s=15.0,
    )
    fallback = ProviderSettings(
        provider="groq",
        model="openai/gpt-oss-20b",
        base_url="https://api.example.com",
        timeout_s=20.0,
    )

    # 1. Negative or zero timeout in ProviderSettings
    with pytest.raises(ValidationError):
        ProviderSettings(
            provider="gemini",
            model="gemini-2.5-flash",
            base_url="https://api.example.com",
            timeout_s=0.0,
        )

    with pytest.raises(ValidationError):
        ProviderSettings(
            provider="gemini",
            model="gemini-2.5-flash",
            base_url="https://api.example.com",
            timeout_s=-5.0,
        )

    # 2. Excessive timeout (> 120s)
    with pytest.raises(ValidationError):
        ProviderSettings(
            provider="gemini",
            model="gemini-2.5-flash",
            base_url="https://api.example.com",
            timeout_s=300.0,
        )

    # 3. Breaker failure threshold out of bounds (< 1 or > 20)
    with pytest.raises(ValidationError):
        GatewayConfig(
            primary=primary,
            fallback=fallback,
            breaker_failure_threshold=0,
        )

    with pytest.raises(ValidationError):
        GatewayConfig(
            primary=primary,
            fallback=fallback,
            breaker_failure_threshold=50,
        )


def test_falsification_unknown_config_field_rejected() -> None:
    """[Gate 1 Falsification] Extra unknown config fields are strictly forbidden."""
    primary = ProviderSettings(
        provider="gemini",
        model="gemini-2.5-flash",
        base_url="https://api.example.com",
        timeout_s=15.0,
    )
    fallback = ProviderSettings(
        provider="groq",
        model="openai/gpt-oss-20b",
        base_url="https://api.example.com",
        timeout_s=20.0,
    )

    with pytest.raises(ValidationError):
        GatewayConfig(
            primary=primary,
            fallback=fallback,
            unauthorized_arbitrary_setting="injected_payload",  # type: ignore[call-arg]
        )


def test_falsification_missing_required_provider_setting() -> None:
    """[Gate 1 Falsification] Missing required provider setting fails validation."""
    with pytest.raises(ValidationError):
        ProviderSettings(  # type: ignore[call-arg]
            provider="gemini",
            # missing model, base_url, timeout_s
        )


def test_falsification_sentinel_secret_isolation() -> None:
    """[Gate 1 Falsification] Sentinel secrets must never leak into error strings."""
    sentinel_key = "SECRET_SENTINEL_AIzaSyD_NEVER_LOG_THIS"

    # 1. Resolve key correctly
    os.environ["GEMINI_API_KEY"] = sentinel_key
    try:
        resolved = resolve_api_key("gemini")
        assert resolved == sentinel_key

        # 2. Provoke a downstream GatewayError and verify sentinel is absent in str/dict
        err = GatewayError(
            category=GatewayErrorCategory.PROVIDER_UNAVAILABLE,
            message="Upstream server returned HTTP 503 Service Unavailable",
            provider="gemini",
            correlation_id="cid-sec-01",
        )
        err_str = str(err)
        err_dict = err.to_dict()

        assert sentinel_key not in err_str
        assert sentinel_key not in str(err_dict)
    finally:
        os.environ.pop("GEMINI_API_KEY", None)


def test_falsification_evidence_bundle_v1_non_interference() -> None:
    """[Gate 1 Verification] Gateway schemas do not alter or extend EvidenceBundle v1."""
    # Instantiating a v1 bundle remains strict and untouched
    bundle = EvidenceBundle(
        company_id="COMP-V1-GW-CHECK",
        raw_features={"current_assets": 100_000.0, "current_liabilities": 50_000.0},
        schema_version="v1",
        pd=0.045,
        credit_rating="BB",
        pd_band=PDBand(p10=0.02, p50=0.045, p90=0.08),
        financial_ratios={"current_ratio": 2.0},
    )
    assert bundle.schema_version == "v1"
    assert bundle.persona_verdicts is None

    # Extra gateway fields injected into EvidenceBundle are strictly forbidden (extra="forbid")
    with pytest.raises(ValidationError):
        EvidenceBundle(
            company_id="COMP-FAIL",
            raw_features={},
            schema_version="v1",
            pd=0.045,
            credit_rating="BB",
            pd_band=PDBand(p10=0.02, p50=0.045, p90=0.08),
            financial_ratios={"current_ratio": 2.0},
            gateway_result="illegal_injection",  # type: ignore[call-arg]
        )
