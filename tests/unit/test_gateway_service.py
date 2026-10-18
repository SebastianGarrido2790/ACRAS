"""Unit tests for gateway routing and bounded outcomes (Stage 6).

Governed by:
    RES-FR-01/02/03/11/12 / GW-FR-04/07/10/12: one primary plus at most one
        fallback attempt, zero same-provider retries, typed controlled dual
        failure, redacted events, mock-transport determinism.
    Execution plan Stage 6 falsification: exactly two attempts on dual failure,
        zero fallback transport calls on primary success, typed failure only.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from typing import Any
from uuid import uuid4

import httpx
import pytest

from src.gateway import (
    BreakerTransitionListener,
    GatewayBreakers,
    GatewayConfig,
    GatewayError,
    GatewayErrorCategory,
    GatewayMessage,
    GatewayMessageRole,
    GatewayRequest,
    GatewayService,
)

_PRIMARY_HOST = "gemini.test"
_FALLBACK_HOST = "groq.test"


def _config(**overrides: Any) -> GatewayConfig:
    data: dict[str, Any] = {
        "primary": {
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "base_url": f"https://{_PRIMARY_HOST}/v1",
            "timeout_s": 15.0,
        },
        "fallback": {
            "provider": "groq",
            "model": "openai/gpt-oss-20b",
            "base_url": f"https://{_FALLBACK_HOST}/v1",
            "timeout_s": 20.0,
        },
        "breaker_failure_threshold": 3,
        "breaker_recovery_timeout_s": 30.0,
        "breaker_half_open_probes": 1,
        "cost_rates": {
            "gemini-2.5-flash": {
                "input_per_m": 0.075,
                "output_per_m": 0.30,
                "rate_date": "2026-10-12",
                "rate_source": "test fixture",
            },
            "openai/gpt-oss-20b": {
                "input_per_m": 0.075,
                "output_per_m": 0.30,
                "rate_date": "2026-10-12",
                "rate_source": "test fixture",
            },
        },
    }
    data.update(overrides)
    return GatewayConfig.model_validate(data)


def _models_by_provider() -> dict[str, str]:
    return {"gemini": "gemini-2.5-flash", "groq": "openai/gpt-oss-20b"}


def _chat_body(text: str) -> dict[str, Any]:
    return {
        "choices": [
            {"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }


def _ok(text: str) -> httpx.Response:
    return httpx.Response(200, json=_chat_body(text))


def _request(
    correlation_id: str = "cid-svc-001",
    content: str = "Assess this SME.",
) -> GatewayRequest:
    return GatewayRequest(
        correlation_id=correlation_id,
        messages=[GatewayMessage(role=GatewayMessageRole.USER, content=content)],
    )


@pytest.fixture(autouse=True)
def _gateway_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")


@pytest.fixture
def events() -> Iterator[tuple[logging.Logger, list[dict[str, Any]]]]:
    records: list[dict[str, Any]] = []

    class _Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(json.loads(record.getMessage()))

    logger = logging.getLogger(f"test-gateway-service-{uuid4().hex}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(_Collect())
    try:
        yield logger, records
    finally:
        logger.handlers.clear()


def _client(
    primary: Callable[[httpx.Request], httpx.Response],
    fallback: Callable[[httpx.Request], httpx.Response],
    counts: dict[str, int],
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == _PRIMARY_HOST:
            counts["gemini"] += 1
            return primary(request)
        if request.url.host == _FALLBACK_HOST:
            counts["groq"] += 1
            return fallback(request)
        raise AssertionError(f"unexpected request host: {request.url.host}")

    return httpx.Client(transport=httpx.MockTransport(handler))


def _outcomes(records: list[dict[str, Any]]) -> list[tuple[str, str, int, str]]:
    return [
        (e["event_type"], e["outcome"], e["attempt"], e["provider"]) for e in records
    ]


def test_primary_success_skips_fallback(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    counts = {"gemini": 0, "groq": 0}
    service = GatewayService(
        _config(),
        client=_client(
            lambda r: _ok("primary answer"),
            lambda r: _ok("fallback answer"),
            counts,
        ),
        logger=logger,
    )

    result = service.complete(_request())

    assert result.provider == "gemini"
    assert result.model == "gemini-2.5-flash"
    assert result.content == "primary answer"
    assert result.fallback_used is False
    assert result.cost_usd is not None
    assert counts == {"gemini": 1, "groq": 0}

    assert _outcomes(records) == [
        ("attempt", "started", 1, "gemini"),
        ("success", "success", 1, "gemini"),
    ]
    success_event = records[1]
    assert success_event["cost_usd"] == result.cost_usd
    assert success_event["usage"]["total_tokens"] == 8
    assert success_event["schema_version"] == "v1"


def test_eligible_primary_failure_routes_to_fallback_once(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    counts = {"gemini": 0, "groq": 0}
    service = GatewayService(
        _config(),
        client=_client(
            lambda r: httpx.Response(503, json={"error": "unavailable"}),
            lambda r: _ok("fallback answer"),
            counts,
        ),
        logger=logger,
    )

    result = service.complete(_request())

    assert result.provider == "groq"
    assert result.model == "openai/gpt-oss-20b"
    assert result.content == "fallback answer"
    assert result.fallback_used is True
    assert counts == {"gemini": 1, "groq": 1}

    assert _outcomes(records) == [
        ("attempt", "started", 1, "gemini"),
        ("failure", "provider_unavailable", 1, "gemini"),
        ("attempt", "started", 2, "groq"),
        ("fallback", "success", 2, "groq"),
    ]
    failure_event = records[1]
    assert failure_event["error_category"] == "provider_unavailable"
    assert failure_event["fallback_used"] is False


def test_primary_timeout_routes_to_fallback_once(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    counts = {"gemini": 0, "groq": 0}

    def timed_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated timeout", request=request)

    service = GatewayService(
        _config(),
        client=_client(timed_out, lambda r: _ok("fallback answer"), counts),
        logger=logger,
    )

    result = service.complete(_request())

    assert result.fallback_used is True
    assert counts == {"gemini": 1, "groq": 1}
    assert ("failure", "timeout_error", 1, "gemini") in _outcomes(records)


def test_primary_429_routes_to_fallback_once(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    counts = {"gemini": 0, "groq": 0}
    service = GatewayService(
        _config(),
        client=_client(
            lambda r: httpx.Response(429, json={"error": "rate limited"}),
            lambda r: _ok("fallback answer"),
            counts,
        ),
        logger=logger,
    )

    result = service.complete(_request())

    assert result.fallback_used is True
    assert counts == {"gemini": 1, "groq": 1}
    assert ("failure", "rate_limit_error", 1, "gemini") in _outcomes(records)


def test_malformed_primary_response_routes_to_fallback_once(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    counts = {"gemini": 0, "groq": 0}
    service = GatewayService(
        _config(),
        client=_client(
            lambda r: httpx.Response(200, json={"choices": []}),
            lambda r: _ok("fallback answer"),
            counts,
        ),
        logger=logger,
    )

    result = service.complete(_request())

    assert result.fallback_used is True
    assert counts == {"gemini": 1, "groq": 1}
    assert ("failure", "invalid_provider_response", 1, "gemini") in _outcomes(records)


def _open_breaker_with(
    breakers: GatewayBreakers, provider: str, logger: logging.Logger
) -> None:
    def attempt() -> None:
        raise GatewayError(
            category=GatewayErrorCategory.TIMEOUT_ERROR,
            message="forced failure for breaker test",
            provider=provider,
        )

    for _ in range(3):
        with pytest.raises(GatewayError):
            breakers.call(provider, attempt)
    assert breakers.state_of(provider) == "open"
    del logger


def test_open_primary_breaker_routes_to_fallback_without_primary_call(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    breakers = GatewayBreakers(
        _config(), listener=BreakerTransitionListener(logger, _models_by_provider())
    )
    _open_breaker_with(breakers, "gemini", logger)
    records.clear()

    counts = {"gemini": 0, "groq": 0}
    service = GatewayService(
        _config(),
        client=_client(lambda r: _ok("primary answer"), lambda r: _ok("fallback answer"), counts),
        logger=logger,
        breakers=breakers,
    )

    result = service.complete(_request())

    assert result.fallback_used is True
    assert result.content == "fallback answer"
    assert counts == {"gemini": 0, "groq": 1}
    assert ("failure", "circuit_breaker_open", 1, "gemini") in _outcomes(records)
    assert ("attempt", "started", 1, "gemini") not in _outcomes(records)


def test_breaker_transitions_emit_single_redacted_event(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    counts = {"gemini": 0, "groq": 0}
    service = GatewayService(
        _config(),
        client=_client(
            lambda r: httpx.Response(503, json={"error": "unavailable"}),
            lambda r: _ok("fallback answer"),
            counts,
        ),
        logger=logger,
    )

    for _ in range(2):
        assert service.complete(_request()).fallback_used is True
    assert not [e for e in records if e["event_type"] == "breaker_transition"]

    assert service.complete(_request()).fallback_used is True
    transitions = [e for e in records if e["event_type"] == "breaker_transition"]
    assert len(transitions) == 1
    transition = transitions[0]
    assert transition["provider"] == "gemini"
    assert transition["outcome"] == "breaker_closed_to_open"
    assert transition["breaker_state"] == "open"
    assert transition["correlation_id"] == "cid-svc-001"


def test_dual_failure_returns_typed_controlled_error(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    counts = {"gemini": 0, "groq": 0}
    service = GatewayService(
        _config(),
        client=_client(
            lambda r: httpx.Response(503, json={"error": "unavailable"}),
            lambda r: httpx.Response(500, json={"error": "boom"}),
            counts,
        ),
        logger=logger,
    )

    with pytest.raises(GatewayError) as exc_info:
        service.complete(_request())

    error = exc_info.value
    assert error.category is GatewayErrorCategory.DUAL_PROVIDER_FAILURE
    assert error.correlation_id == "cid-svc-001"
    assert "provider_unavailable" in error.message
    assert isinstance(error.cause_error, GatewayError)
    assert error.cause_error.category is GatewayErrorCategory.PROVIDER_UNAVAILABLE
    assert counts == {"gemini": 1, "groq": 1}

    assert _outcomes(records) == [
        ("attempt", "started", 1, "gemini"),
        ("failure", "provider_unavailable", 1, "gemini"),
        ("attempt", "started", 2, "groq"),
        ("failure", "provider_unavailable", 2, "groq"),
        ("failure", "dual_provider_failure", 2, "groq"),
    ]
    terminal = records[-1]
    assert terminal["error_category"] == "dual_provider_failure"
    assert terminal["fallback_used"] is True


def test_open_fallback_breaker_yields_dual_failure_without_fallback_call(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    breakers = GatewayBreakers(
        _config(), listener=BreakerTransitionListener(logger, _models_by_provider())
    )
    _open_breaker_with(breakers, "groq", logger)
    records.clear()

    counts = {"gemini": 0, "groq": 0}
    service = GatewayService(
        _config(),
        client=_client(
            lambda r: httpx.Response(503, json={"error": "unavailable"}),
            lambda r: _ok("fallback answer"),
            counts,
        ),
        logger=logger,
        breakers=breakers,
    )

    with pytest.raises(GatewayError) as exc_info:
        service.complete(_request())

    error = exc_info.value
    assert error.category is GatewayErrorCategory.DUAL_PROVIDER_FAILURE
    assert isinstance(error.cause_error, GatewayError)
    assert error.cause_error.category is GatewayErrorCategory.CIRCUIT_BREAKER_OPEN
    assert counts == {"gemini": 1, "groq": 0}

    assert ("failure", "provider_unavailable", 1, "gemini") in _outcomes(records)
    assert ("failure", "circuit_breaker_open", 2, "groq") in _outcomes(records)


def test_deterministic_4xx_primary_failure_fails_fast(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    counts = {"gemini": 0, "groq": 0}
    service = GatewayService(
        _config(),
        client=_client(
            lambda r: httpx.Response(400, json={"error": "bad request"}),
            lambda r: _ok("fallback answer"),
            counts,
        ),
        logger=logger,
    )

    with pytest.raises(GatewayError) as exc_info:
        service.complete(_request())

    assert exc_info.value.category is GatewayErrorCategory.INVALID_PROVIDER_RESPONSE
    assert counts == {"gemini": 1, "groq": 0}
    assert not [e for e in records if e["provider"] == "groq"]


def test_missing_primary_credential_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    counts = {"gemini": 0, "groq": 0}
    service = GatewayService(
        _config(),
        client=_client(lambda r: _ok("primary answer"), lambda r: _ok("fallback answer"), counts),
        logger=logger,
    )

    with pytest.raises(GatewayError) as exc_info:
        service.complete(_request())

    error = exc_info.value
    assert error.category is GatewayErrorCategory.CONFIG_OR_AUTH_ERROR
    assert error.status_code is None
    assert counts == {"gemini": 0, "groq": 0}
    assert ("failure", "config_or_auth_error", 1, "gemini") in _outcomes(records)


def test_events_redact_prompt_and_borrower_sentinels(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    counts = {"gemini": 0, "groq": 0}
    service = GatewayService(
        _config(),
        client=_client(
            lambda r: httpx.Response(503, json={"error": "unavailable"}),
            lambda r: httpx.Response(500, json={"error": "boom"}),
            counts,
        ),
        logger=logger,
    )
    sentinel_request = _request(
        content="PROMPT_SENTINEL_ASSESS_THIS_SME for BORROWER_SENTINEL_ACME_CORP"
    )

    with pytest.raises(GatewayError):
        service.complete(sentinel_request)

    rendered = json.dumps(records)
    for sentinel in (
        "PROMPT_SENTINEL_ASSESS_THIS_SME",
        "BORROWER_SENTINEL_ACME_CORP",
        "test-gemini-key",
        "test-groq-key",
    ):
        assert sentinel not in rendered


def test_service_rejects_non_policy_attempt_settings() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        GatewayService(_config(max_attempts=3))
    with pytest.raises(ValueError, match="retries_per_provider"):
        GatewayService(_config(retries_per_provider=1))


def test_service_rejects_unknown_provider() -> None:
    data = _config().model_dump()
    data["primary"]["provider"] = "openrouter"
    with pytest.raises(ValueError, match="openrouter"):
        GatewayService(GatewayConfig.model_validate(data))
