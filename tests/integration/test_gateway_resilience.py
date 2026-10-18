"""Gateway resilience & integration acceptance suite (Stage 7 / RES-T07, GW-T08).

Governed by:
    RES-FR-01..14 and the approved clarification answers (2026-10-12): bounded
        primary -> fallback routing (max two attempts), independent
        process-local breakers, typed controlled dual failure, structured
        redacted events, deterministic mock-transport acceptance.
    RES-FR-13 / GW-FR-12: routine CI makes no live provider call and needs no
        credentials; every fault is injected through an injectable
        ``httpx.MockTransport``.
    GW-FR-07/08/09/10: complete auditable events; unknown usage/cost stays
        unknown; prompts, completions, credentials, and borrower data never
        appear in the log stream.
    INV-1 / INV-6 (ADR-001 / ADR-006) and RES-FR-14: the gateway neither reads
        nor writes deterministic Tier 1-2 state and never mutates EvidenceBundle
        v1; this suite touches only the gateway boundary.
    Execution plan Stage 7 falsification: invert one critical assertion in a
        local variant, confirm the deliberately wrong expectation fails, then
        discard the mutation (recorded in the Stage 7 evidence, not committed).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pybreaker
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

_PRIMARY_HOST = "gemini.integration.test"
_FALLBACK_HOST = "groq.integration.test"

_REQUIRED_EVENT_KEYS = {
    "schema_version",
    "timestamp",
    "correlation_id",
    "event_type",
    "provider",
    "model",
    "attempt",
    "outcome",
    "latency_ms",
    "fallback_used",
    "breaker_state",
    "usage",
    "cost_usd",
    "error_category",
    "error_message",
}


# ---------------------------------------------------------------------------
# Deterministic clock for pybreaker's open -> half-open transition
# ---------------------------------------------------------------------------

_CLOCK = {"offset_s": 0.0}


class _ClockDatetime(datetime):
    """datetime whose ``now`` is shifted by a controllable offset."""

    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        return datetime.now(tz) + timedelta(seconds=_CLOCK["offset_s"])


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[float], None]:
    """Advance pybreaker's internal wall clock without sleeping (deterministic)."""
    _CLOCK["offset_s"] = 0.0
    monkeypatch.setattr(pybreaker, "datetime", _ClockDatetime)

    def advance(seconds: float) -> None:
        _CLOCK["offset_s"] += seconds

    return advance


# ---------------------------------------------------------------------------
# Harness: config, mock transport routing, event capture
# ---------------------------------------------------------------------------


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


def _chat_body(text: str, *, usage: bool = True, finish: str = "stop") -> dict[str, Any]:
    body: dict[str, Any] = {
        "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": finish}]
    }
    if usage:
        body["usage"] = {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
    return body


def _ok(text: str, *, usage: bool = True) -> httpx.Response:
    return httpx.Response(200, json=_chat_body(text, usage=usage))


def _status(code: int) -> httpx.Response:
    return httpx.Response(code, json={"error": "provider error"})


@dataclass
class _Routing:
    """A shared mock transport that routes by host and records every request."""

    primary: Callable[[httpx.Request], httpx.Response]
    fallback: Callable[[httpx.Request], httpx.Response]
    primary_requests: list[httpx.Request] = field(default_factory=list)
    fallback_requests: list[httpx.Request] = field(default_factory=list)

    def _handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == _PRIMARY_HOST:
            self.primary_requests.append(request)
            return self.primary(request)
        if request.url.host == _FALLBACK_HOST:
            self.fallback_requests.append(request)
            return self.fallback(request)
        raise AssertionError(f"unexpected request host: {request.url.host}")

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self._handler))

    def counts(self) -> tuple[int, int]:
        return (len(self.primary_requests), len(self.fallback_requests))


def _request(
    correlation_id: str = "cid-int-001",
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

    logger = logging.getLogger(f"test-gateway-integration-{uuid4().hex}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(_Collect())
    try:
        yield logger, records
    finally:
        logger.handlers.clear()


def _service(
    routing: _Routing,
    logger: logging.Logger,
    *,
    config: GatewayConfig | None = None,
    breakers: GatewayBreakers | None = None,
) -> GatewayService:
    return GatewayService(
        config if config is not None else _config(),
        client=routing.client(),
        logger=logger,
        breakers=breakers,
    )


def _breakers(logger: logging.Logger) -> GatewayBreakers:
    return GatewayBreakers(
        _config(), listener=BreakerTransitionListener(logger, _models_by_provider())
    )


def _outcomes(records: list[dict[str, Any]]) -> list[tuple[str, str, int, str]]:
    return [(e["event_type"], e["outcome"], e["attempt"], e["provider"]) for e in records]


def _open_primary_breaker(service: GatewayService) -> None:
    """Drive three eligible primary failures so Gemini's breaker trips.

    Each call is served by the fallback (primary failure is eligible), so the
    gateway succeeds; only the primary breaker accumulates failures.
    """
    for _ in range(3):
        assert service.complete(_request()).fallback_used is True


# ---------------------------------------------------------------------------
# 1. Routing matrix: primary success + eligible failure paths
# ---------------------------------------------------------------------------


def test_primary_success_skips_fallback(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    routing = _Routing(lambda r: _ok("primary answer"), lambda r: _ok("fallback answer"))
    service = _service(routing, logger)

    result = service.complete(_request())

    assert result.provider == "gemini"
    assert result.model == "gemini-2.5-flash"
    assert result.content == "primary answer"
    assert result.fallback_used is False
    assert routing.counts() == (1, 0)
    assert _outcomes(records) == [
        ("attempt", "started", 1, "gemini"),
        ("success", "success", 1, "gemini"),
    ]


def test_primary_timeout_falls_back_once(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events

    def timed_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated timeout", request=request)

    routing = _Routing(timed_out, lambda r: _ok("fallback answer"))
    service = _service(routing, logger)

    result = service.complete(_request())

    assert result.fallback_used is True
    assert result.provider == "groq"
    assert routing.counts() == (1, 1)
    assert _outcomes(records) == [
        ("attempt", "started", 1, "gemini"),
        ("failure", "timeout_error", 1, "gemini"),
        ("attempt", "started", 2, "groq"),
        ("fallback", "success", 2, "groq"),
    ]


def test_primary_connection_failure_falls_back_once(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    routing = _Routing(unreachable, lambda r: _ok("fallback answer"))
    service = _service(routing, logger)

    result = service.complete(_request())

    assert result.fallback_used is True
    assert routing.counts() == (1, 1)
    assert ("failure", "connection_error", 1, "gemini") in _outcomes(records)


def test_primary_eligible_server_error_falls_back_once(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    routing = _Routing(lambda r: _status(503), lambda r: _ok("fallback answer"))
    service = _service(routing, logger)

    result = service.complete(_request())

    assert result.fallback_used is True
    assert routing.counts() == (1, 1)
    assert ("failure", "provider_unavailable", 1, "gemini") in _outcomes(records)


def test_primary_429_falls_back_once_without_same_provider_retry(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    routing = _Routing(lambda r: _status(429), lambda r: _ok("fallback answer"))
    service = _service(routing, logger)

    result = service.complete(_request())

    assert result.fallback_used is True
    # Primary invoked exactly once: no same-provider retry on rate limit.
    assert routing.counts() == (1, 1)
    assert ("failure", "rate_limit_error", 1, "gemini") in _outcomes(records)


def test_primary_provider_auth_rejection_falls_back_once(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    routing = _Routing(lambda r: _status(401), lambda r: _ok("fallback answer"))
    service = _service(routing, logger)

    result = service.complete(_request())

    assert result.fallback_used is True
    assert routing.counts() == (1, 1)
    assert ("failure", "config_or_auth_error", 1, "gemini") in _outcomes(records)


def test_primary_local_credential_fault_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    routing = _Routing(lambda r: _ok("primary answer"), lambda r: _ok("fallback answer"))
    service = _service(routing, logger)

    with pytest.raises(GatewayError) as exc_info:
        service.complete(_request())

    error = exc_info.value
    assert error.category is GatewayErrorCategory.CONFIG_OR_AUTH_ERROR
    assert error.status_code is None  # local fault, not a provider rejection
    # Never retried as a transient provider failure (RES-FR-08).
    assert routing.counts() == (0, 0)
    assert not [e for e in records if e["provider"] == "groq"]


def test_malformed_primary_success_falls_back_once(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    routing = _Routing(
        lambda r: httpx.Response(200, json={"choices": []}),
        lambda r: _ok("fallback answer"),
    )
    service = _service(routing, logger)

    result = service.complete(_request())

    assert result.fallback_used is True
    assert routing.counts() == (1, 1)
    assert ("failure", "invalid_provider_response", 1, "gemini") in _outcomes(records)


def test_deterministic_primary_4xx_rejection_fails_fast(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    routing = _Routing(lambda r: _status(400), lambda r: _ok("fallback answer"))
    service = _service(routing, logger)

    with pytest.raises(GatewayError) as exc_info:
        service.complete(_request())

    assert exc_info.value.category is GatewayErrorCategory.INVALID_PROVIDER_RESPONSE
    assert routing.counts() == (1, 0)
    assert not [e for e in records if e["provider"] == "groq"]


# ---------------------------------------------------------------------------
# 2. Dual failure and attempt bounds
# ---------------------------------------------------------------------------


def test_fallback_failure_yields_typed_dual_failure(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    routing = _Routing(lambda r: _status(503), lambda r: _status(500))
    service = _service(routing, logger)

    with pytest.raises(GatewayError) as exc_info:
        service.complete(_request("cid-int-dual"))

    error = exc_info.value
    assert error.category is GatewayErrorCategory.DUAL_PROVIDER_FAILURE
    assert error.correlation_id == "cid-int-dual"
    assert isinstance(error.cause_error, GatewayError)
    assert error.cause_error.category is GatewayErrorCategory.PROVIDER_UNAVAILABLE
    assert routing.counts() == (1, 1)
    terminal = records[-1]
    assert terminal["event_type"] == "failure"
    assert terminal["outcome"] == "dual_provider_failure"
    assert terminal["fallback_used"] is True


def test_repeated_dual_failures_never_exceed_two_attempts_per_call(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    routing = _Routing(lambda r: _status(503), lambda r: _status(500))
    service = _service(routing, logger)

    for call in range(1, 4):
        with pytest.raises(GatewayError):
            service.complete(_request())
        assert routing.counts() == (call, call)
    assert len(records) > 0


def test_both_breakers_open_yields_dual_failure_without_provider_calls(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    routing = _Routing(lambda r: _status(503), lambda r: _status(500))
    service = _service(routing, logger)

    # Three consecutive eligible failures trip both provider breakers.
    for _ in range(3):
        with pytest.raises(GatewayError):
            service.complete(_request())
    assert routing.counts() == (3, 3)

    with pytest.raises(GatewayError) as exc_info:
        service.complete(_request())

    error = exc_info.value
    assert error.category is GatewayErrorCategory.DUAL_PROVIDER_FAILURE
    assert isinstance(error.cause_error, GatewayError)
    assert error.cause_error.category is GatewayErrorCategory.CIRCUIT_BREAKER_OPEN
    # Both breakers open: no provider request is sent on the terminal call.
    assert routing.counts() == (3, 3)
    assert ("failure", "circuit_breaker_open", 1, "gemini") in _outcomes(records)
    assert ("failure", "circuit_breaker_open", 2, "groq") in _outcomes(records)


# ---------------------------------------------------------------------------
# 3. Breaker state machine: open, skip, half-open recovery, re-open
# ---------------------------------------------------------------------------


def test_open_primary_breaker_routes_to_fallback_without_primary_request(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    state: dict[str, Callable[[httpx.Request], httpx.Response]] = {
        "primary": lambda r: _status(503)
    }
    routing = _Routing(lambda r: state["primary"](r), lambda r: _ok("fallback answer"))
    breakers = _breakers(logger)
    service = _service(routing, logger, breakers=breakers)

    _open_primary_breaker(service)
    assert breakers.state_of("gemini") == "open"

    marker = len(records)
    result = service.complete(_request())

    assert result.fallback_used is True
    assert result.provider == "groq"
    # Primary is skipped: no transport call, no attempt event for Gemini.
    assert routing.counts() == (3, 4)
    tail = _outcomes(records[marker:])
    assert ("attempt", "started", 1, "gemini") not in tail
    assert ("failure", "circuit_breaker_open", 1, "gemini") in tail


def test_consecutive_eligible_failures_open_primary_breaker(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    routing = _Routing(lambda r: _status(503), lambda r: _ok("fallback answer"))
    breakers = _breakers(logger)
    service = _service(routing, logger, breakers=breakers)

    for _ in range(2):
        assert service.complete(_request()).fallback_used is True
    assert breakers.state_of("gemini") == "closed"
    assert breakers.failure_count("gemini") == 2
    assert not [e for e in records if e["event_type"] == "breaker_transition"]

    assert service.complete(_request()).fallback_used is True
    assert breakers.state_of("gemini") == "open"
    transitions = [e for e in records if e["event_type"] == "breaker_transition"]
    assert len(transitions) == 1
    assert transitions[0]["provider"] == "gemini"
    assert transitions[0]["outcome"] == "breaker_closed_to_open"
    assert transitions[0]["breaker_state"] == "open"
    assert transitions[0]["correlation_id"] == "cid-int-001"


def test_recovered_primary_is_used_after_open_interval(
    clock: Callable[[float], None],
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    state: dict[str, Callable[[httpx.Request], httpx.Response]] = {
        "primary": lambda r: _status(503)
    }
    routing = _Routing(lambda r: state["primary"](r), lambda r: _ok("fallback answer"))
    breakers = _breakers(logger)
    service = _service(routing, logger, breakers=breakers)

    _open_primary_breaker(service)
    assert breakers.state_of("gemini") == "open"

    clock(31.0)
    state["primary"] = lambda r: _ok("primary recovered")
    fallback_before = len(routing.fallback_requests)

    result = service.complete(_request())

    # The single half-open probe succeeds and closes the breaker; fallback unused.
    assert result.provider == "gemini"
    assert result.content == "primary recovered"
    assert result.fallback_used is False
    assert breakers.state_of("gemini") == "closed"
    assert len(routing.fallback_requests) == fallback_before
    recovery = [
        (e["breaker_state"], e["outcome"])
        for e in records
        if e["event_type"] == "breaker_transition" and e["breaker_state"] == "closed"
    ]
    assert ("closed", "breaker_half_open_to_closed") in recovery

    # Subsequent calls keep using the recovered primary with no fallback.
    for _ in range(2):
        assert service.complete(_request()).provider == "gemini"
    assert len(routing.fallback_requests) == fallback_before


def test_failed_half_open_probe_reopens_breaker(
    clock: Callable[[float], None],
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    routing = _Routing(lambda r: _status(503), lambda r: _ok("fallback answer"))
    breakers = _breakers(logger)
    service = _service(routing, logger, breakers=breakers)

    _open_primary_breaker(service)
    clock(31.0)

    # First post-interval call is the single probe; it fails and reopens.
    assert service.complete(_request()).fallback_used is True
    assert breakers.state_of("gemini") == "open"
    assert routing.counts() == (4, 4)

    # Next call is skipped immediately without advancing the clock.
    assert service.complete(_request()).fallback_used is True
    assert routing.counts() == (4, 5)
    tail = [e for e in records if e["event_type"] == "breaker_transition"]
    assert tail[-1]["outcome"] == "breaker_half_open_to_open"


def test_provider_breaker_state_is_independent(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    routing = _Routing(lambda r: _status(503), lambda r: _ok("fallback answer"))
    breakers = _breakers(logger)
    service = _service(routing, logger, breakers=breakers)

    _open_primary_breaker(service)
    assert breakers.state_of("gemini") == "open"
    assert breakers.state_of("groq") == "closed"
    assert breakers.failure_count("groq") == 0

    result = service.complete(_request())
    assert result.provider == "groq"
    assert breakers.state_of("groq") == "closed"
    assert breakers.failure_count("gemini") == 3
    assert not [
        e for e in records if e["event_type"] == "breaker_transition" and e["provider"] == "groq"
    ]


def test_half_open_probe_is_serialized_to_one_in_flight(
    clock: Callable[[float], None],
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, _records = events
    state: dict[str, Callable[[httpx.Request], httpx.Response]] = {
        "primary": lambda r: _status(503)
    }
    entered = threading.Event()
    release = threading.Event()
    state_lock = threading.Lock()
    counters = {"calls": 0, "active": 0, "max_active": 0}

    def blocking_primary(request: httpx.Request) -> httpx.Response:
        with state_lock:
            counters["calls"] += 1
            counters["active"] += 1
            counters["max_active"] = max(counters["max_active"], counters["active"])
        entered.set()
        release.wait(timeout=5.0)
        with state_lock:
            counters["active"] -= 1
        return _ok("probe ok")

    routing = _Routing(lambda r: state["primary"](r), lambda r: _ok("fallback answer"))
    breakers = _breakers(logger)
    service = _service(routing, logger, breakers=breakers)

    _open_primary_breaker(service)
    clock(31.0)
    state["primary"] = blocking_primary
    routing.primary_requests.clear()
    routing.fallback_requests.clear()

    errors: list[BaseException] = []

    def worker() -> None:
        try:
            service.complete(_request())
        except BaseException as exc:  # pragma: no cover - failure path asserted below
            errors.append(exc)

    first = threading.Thread(target=worker)
    second = threading.Thread(target=worker)
    first.start()
    assert entered.wait(timeout=5.0)
    second.start()
    time.sleep(0.2)
    with state_lock:
        assert counters["calls"] == 1
    release.set()
    first.join(timeout=5.0)
    second.join(timeout=5.0)

    assert errors == []
    assert counters["max_active"] == 1
    assert counters["calls"] == 2
    assert routing.counts() == (2, 0)
    assert breakers.state_of("gemini") == "closed"


# ---------------------------------------------------------------------------
# 4. Event completeness, correlation, ordering, unknowns, redaction
# ---------------------------------------------------------------------------


def test_event_sequence_and_metadata_on_fallback_success(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    routing = _Routing(lambda r: _status(503), lambda r: _ok("fallback answer"))
    service = _service(routing, logger)

    service.complete(_request("cid-int-evt"))

    assert _outcomes(records) == [
        ("attempt", "started", 1, "gemini"),
        ("failure", "provider_unavailable", 1, "gemini"),
        ("attempt", "started", 2, "groq"),
        ("fallback", "success", 2, "groq"),
    ]
    for record in records:
        assert set(record) >= _REQUIRED_EVENT_KEYS
        assert record["correlation_id"] == "cid-int-evt"
        assert record["schema_version"] == "v1"

    failure, success = records[1], records[3]
    assert failure["fallback_used"] is False
    assert failure["error_category"] == "provider_unavailable"
    assert failure["error_message"] == "Provider unavailable or server-side failure."
    assert success["provider"] == "groq"
    assert success["model"] == "openai/gpt-oss-20b"
    assert success["attempt"] == 2
    assert success["fallback_used"] is True


def test_redaction_prevents_prompt_response_secret_borrower_leakage(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    prompt_sentinel = "PROMPT_SENTINEL_INTEGRATION_ASSESS"
    borrower_sentinel = "BORROWER_SENTINEL_INTEGRATION_LTD"
    response_sentinel = "RESPONSE_SENTINEL_INTEGRATION_APPROVE"
    secret_sentinel = "gsk_INTEGRATION_SENTINEL_1234567890"

    routing = _Routing(
        lambda r: httpx.Response(503, json={"error": f"{response_sentinel} {secret_sentinel}"}),
        lambda r: httpx.Response(500, json={"error": response_sentinel}),
    )
    service = _service(routing, logger)

    with pytest.raises(GatewayError):
        service.complete(_request(content=f"{prompt_sentinel} for {borrower_sentinel}"))

    rendered = json.dumps(records)
    for sentinel in (
        prompt_sentinel,
        borrower_sentinel,
        response_sentinel,
        secret_sentinel,
        "test-gemini-key",
        "test-groq-key",
    ):
        assert sentinel not in rendered
    assert records  # required metadata still emitted
    assert all(record["correlation_id"] == "cid-int-001" for record in records)


def test_unknown_usage_keeps_cost_unknown(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, records = events
    routing = _Routing(lambda r: _status(503), lambda r: _ok("fallback answer", usage=False))
    service = _service(routing, logger)

    result = service.complete(_request())

    assert result.usage is None
    assert result.cost_usd is None
    success = records[-1]
    assert success["outcome"] == "success"
    assert success["usage"] is None
    assert success["cost_usd"] is None


def test_timeout_bounds_propagate_to_shared_transport(
    events: tuple[logging.Logger, list[dict[str, Any]]],
) -> None:
    logger, _records = events

    def timed_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated timeout", request=request)

    routing = _Routing(timed_out, lambda r: _ok("fallback answer"))
    service = _service(routing, logger)

    service.complete(_request())

    primary_timeout = routing.primary_requests[0].extensions["timeout"]
    fallback_timeout = routing.fallback_requests[0].extensions["timeout"]
    assert primary_timeout["read"] == pytest.approx(15.0)
    assert primary_timeout["connect"] == pytest.approx(15.0)
    assert fallback_timeout["read"] == pytest.approx(20.0)
    assert fallback_timeout["connect"] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# 5. Opt-in live smoke (never part of routine CI; secret-safe)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("ACRAS_LIVE_GATEWAY_SMOKE"),
    reason="Opt-in live provider smoke test; set ACRAS_LIVE_GATEWAY_SMOKE=1 to run.",
)
def test_live_gateway_smoke_opt_in() -> None:
    """Live Gemini -> Groq smoke test; opt-in only, secret-safe, no credential output."""
    for var in ("GEMINI_API_KEY", "GROQ_API_KEY"):
        if not os.environ.get(var):
            pytest.skip(f"Live smoke requested but {var} is not set.")

    config = GatewayConfig.model_validate(
        {
            "primary": {
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                "timeout_s": 15.0,
            },
            "fallback": {
                "provider": "groq",
                "model": "openai/gpt-oss-20b",
                "base_url": "https://api.groq.com/openai/v1",
                "timeout_s": 20.0,
            },
        }
    )
    service = GatewayService(config)
    result = service.complete(
        _request(f"cid-smoke-{uuid4().hex}", content="Reply with the single word: ACK.")
    )

    assert result.content.strip() != ""
    assert result.provider in {"gemini", "groq"}
    assert result.latency_ms >= 0.0
