"""Unit tests for gateway failure eligibility and provider breakers (Stage 5).

Governed by:
    RES-FR-04..10 / D3-03: independent breakers, approved failure matrix,
        bounded transitions, process-local state, zero same-provider retries.
    Clarification answers 2026-10-12 (429, auth, malformed, probe scope).
    Execution plan Stage 5 falsification: threshold crossing, open-state skip,
    deterministic interval advance, single-probe recover/reopen, independence.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import pybreaker
import pytest

from src.gateway import (
    GatewayBreakers,
    GatewayConfig,
    GatewayError,
    GatewayErrorCategory,
    is_breaker_failure,
    is_fallback_eligible,
)
from src.gateway.providers.base import classify_http_error

_CLOCK_OFFSET = {"seconds": 0.0}


class _OffsetDatetime(datetime):
    """datetime whose ``now`` is shifted by a controllable offset."""

    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        return datetime.now(tz) + timedelta(seconds=_CLOCK_OFFSET["seconds"])


def _gateway_config() -> GatewayConfig:
    return GatewayConfig.model_validate(
        {
            "primary": {
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "base_url": "https://example.test/gemini",
                "timeout_s": 15.0,
            },
            "fallback": {
                "provider": "groq",
                "model": "openai/gpt-oss-20b",
                "base_url": "https://example.test/groq",
                "timeout_s": 20.0,
            },
            "breaker_failure_threshold": 3,
            "breaker_recovery_timeout_s": 30.0,
            "breaker_half_open_probes": 1,
        }
    )


@pytest.fixture
def pybreaker_clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[float], None]:
    """Deterministic control of pybreaker's internal wall clock (no sleeps)."""
    _CLOCK_OFFSET["seconds"] = 0.0
    monkeypatch.setattr(pybreaker, "datetime", _OffsetDatetime)

    def advance(seconds: float) -> None:
        _CLOCK_OFFSET["seconds"] += seconds

    return advance


def _timeout_error(provider: str = "gemini") -> GatewayError:
    return GatewayError(
        category=GatewayErrorCategory.TIMEOUT_ERROR,
        message="Provider request timed out after 15.0s.",
        correlation_id="cid-test",
        provider=provider,
    )


def _force_open(breakers: GatewayBreakers, provider: str) -> None:
    def attempt() -> None:
        raise _timeout_error(provider=provider)

    for _ in range(3):
        with pytest.raises(GatewayError):
            breakers.call(provider, attempt)
    assert breakers.state_of(provider) == "open"


def test_closed_to_open_after_three_consecutive_eligible_failures(
    pybreaker_clock: Callable[[float], None],
) -> None:
    del pybreaker_clock
    breakers = GatewayBreakers(_gateway_config())
    calls = 0

    def attempt() -> None:
        nonlocal calls
        calls += 1
        raise _timeout_error()

    for _ in range(2):
        with pytest.raises(GatewayError) as exc_info:
            breakers.call("gemini", attempt, correlation_id="cid-a")
        assert exc_info.value.category is GatewayErrorCategory.TIMEOUT_ERROR
    assert breakers.state_of("gemini") == "closed"
    assert breakers.failure_count("gemini") == 2

    with pytest.raises(GatewayError) as trip_info:
        breakers.call("gemini", attempt, correlation_id="cid-b")
    assert trip_info.value.category is GatewayErrorCategory.TIMEOUT_ERROR
    assert breakers.state_of("gemini") == "open"
    assert calls == 3


def test_open_breaker_skips_provider_without_invoking_attempt() -> None:
    breakers = GatewayBreakers(_gateway_config())
    _force_open(breakers, "gemini")
    calls = 0

    def attempt() -> None:
        nonlocal calls
        calls += 1

    with pytest.raises(GatewayError) as exc_info:
        breakers.call("gemini", attempt, correlation_id="cid-skip")
    err = exc_info.value
    assert err.category is GatewayErrorCategory.CIRCUIT_BREAKER_OPEN
    assert err.provider == "gemini"
    assert err.correlation_id == "cid-skip"
    assert calls == 0


def test_half_open_probe_success_closes_breaker(pybreaker_clock: Callable[[float], None]) -> None:
    breakers = GatewayBreakers(_gateway_config())
    _force_open(breakers, "gemini")

    pybreaker_clock(29.0)
    with pytest.raises(GatewayError) as exc_info:
        breakers.call("gemini", lambda: None)
    assert exc_info.value.category is GatewayErrorCategory.CIRCUIT_BREAKER_OPEN

    pybreaker_clock(2.0)
    calls = 0

    def probe() -> str:
        nonlocal calls
        calls += 1
        return "recovered"

    assert breakers.call("gemini", probe) == "recovered"
    assert calls == 1
    assert breakers.state_of("gemini") == "closed"
    assert breakers.failure_count("gemini") == 0


def test_half_open_probe_failure_reopens_breaker(pybreaker_clock: Callable[[float], None]) -> None:
    breakers = GatewayBreakers(_gateway_config())
    _force_open(breakers, "gemini")
    pybreaker_clock(31.0)

    def failing_probe() -> None:
        raise _timeout_error()

    with pytest.raises(GatewayError) as exc_info:
        breakers.call("gemini", failing_probe)
    assert exc_info.value.category is GatewayErrorCategory.TIMEOUT_ERROR
    assert breakers.state_of("gemini") == "open"

    calls = 0

    def attempt() -> None:
        nonlocal calls
        calls += 1

    with pytest.raises(GatewayError) as skip_info:
        breakers.call("gemini", attempt)
    assert skip_info.value.category is GatewayErrorCategory.CIRCUIT_BREAKER_OPEN
    assert calls == 0

    pybreaker_clock(31.0)
    assert breakers.call("gemini", lambda: "ok") == "ok"
    assert breakers.state_of("gemini") == "closed"


def test_repeated_failure_reopens_after_recovery(pybreaker_clock: Callable[[float], None]) -> None:
    breakers = GatewayBreakers(_gateway_config())
    _force_open(breakers, "groq")

    pybreaker_clock(31.0)
    assert breakers.call("groq", lambda: "recovered") == "recovered"
    assert breakers.state_of("groq") == "closed"

    _force_open(breakers, "groq")
    assert breakers.state_of("groq") == "open"


def test_provider_breakers_are_independent(pybreaker_clock: Callable[[float], None]) -> None:
    breakers = GatewayBreakers(_gateway_config())
    _force_open(breakers, "gemini")

    assert breakers.state_of("gemini") == "open"
    assert breakers.state_of("groq") == "closed"
    assert breakers.failure_count("groq") == 0

    assert breakers.call("groq", lambda: "fallback-ok") == "fallback-ok"
    assert breakers.failure_count("gemini") == 3
    assert breakers.failure_count("groq") == 0

    _force_open(breakers, "groq")
    pybreaker_clock(31.0)
    assert breakers.call("gemini", lambda: "primary-ok") == "primary-ok"
    assert breakers.state_of("gemini") == "closed"
    assert breakers.state_of("groq") == "open"
    assert breakers.failure_count("gemini") == 0


def test_non_eligible_failures_never_open_breaker() -> None:
    breakers = GatewayBreakers(_gateway_config())
    calls = 0

    def attempt() -> None:
        nonlocal calls
        calls += 1
        raise GatewayError(
            category=GatewayErrorCategory.CALLER_INPUT_ERROR,
            message="Gateway request failed input validation.",
            provider="gemini",
        )

    for _ in range(5):
        with pytest.raises(GatewayError):
            breakers.call("gemini", attempt)
    assert calls == 5
    assert breakers.state_of("gemini") == "closed"
    assert breakers.failure_count("gemini") == 0


def test_non_eligible_outcome_breaks_consecutive_eligible_streak() -> None:
    breakers = GatewayBreakers(_gateway_config())

    def eligible() -> None:
        raise _timeout_error()

    def non_eligible() -> None:
        raise GatewayError(
            category=GatewayErrorCategory.CALLER_INPUT_ERROR,
            message="Gateway request failed input validation.",
            provider="gemini",
        )

    for _ in range(2):
        with pytest.raises(GatewayError):
            breakers.call("gemini", eligible)
    with pytest.raises(GatewayError):
        breakers.call("gemini", non_eligible)
    assert breakers.failure_count("gemini") == 0

    for _ in range(2):
        with pytest.raises(GatewayError):
            breakers.call("gemini", eligible)
    assert breakers.state_of("gemini") == "closed"
    with pytest.raises(GatewayError):
        breakers.call("gemini", eligible)
    assert breakers.state_of("gemini") == "open"


def test_half_open_probes_are_serialized_to_one_in_flight(
    pybreaker_clock: Callable[[float], None],
) -> None:
    breakers = GatewayBreakers(_gateway_config())
    _force_open(breakers, "gemini")
    pybreaker_clock(31.0)

    entered = threading.Event()
    release = threading.Event()
    state_lock = threading.Lock()
    counters = {"calls": 0, "active": 0, "max_active": 0}

    def guarded() -> str:
        with state_lock:
            counters["calls"] += 1
            counters["active"] += 1
            counters["max_active"] = max(counters["max_active"], counters["active"])
        entered.set()
        release.wait(timeout=5.0)
        with state_lock:
            counters["active"] -= 1
        return "probe-ok"

    errors: list[BaseException] = []

    def worker() -> None:
        try:
            breakers.call("gemini", guarded)
        except Exception as exc:
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
    assert counters["calls"] == 2
    assert counters["max_active"] == 1
    assert breakers.state_of("gemini") == "closed"


def test_unknown_provider_has_no_breaker() -> None:
    breakers = GatewayBreakers(_gateway_config())
    with pytest.raises(ValueError, match="openrouter"):
        breakers.call("openrouter", lambda: None)
    with pytest.raises(ValueError, match="openrouter"):
        breakers.state_of("openrouter")


def test_same_provider_legs_are_rejected() -> None:
    data = _gateway_config().model_dump()
    data["fallback"]["provider"] = "gemini"
    with pytest.raises(ValueError, match="distinct providers"):
        GatewayBreakers(GatewayConfig.model_validate(data))


@pytest.mark.parametrize(
    "category",
    [
        GatewayErrorCategory.TIMEOUT_ERROR,
        GatewayErrorCategory.CONNECTION_ERROR,
        GatewayErrorCategory.RATE_LIMIT_ERROR,
        GatewayErrorCategory.PROVIDER_UNAVAILABLE,
    ],
)
def test_availability_faults_are_fallback_eligible(category: GatewayErrorCategory) -> None:
    error = GatewayError(category=category, message="availability fault", provider="gemini")
    assert is_fallback_eligible(error) is True
    assert is_breaker_failure(error) is True


def test_provider_side_auth_rejection_is_fallback_eligible() -> None:
    error = GatewayError(
        category=GatewayErrorCategory.CONFIG_OR_AUTH_ERROR,
        message="Provider returned HTTP 401.",
        provider="gemini",
        status_code=401,
    )
    assert is_fallback_eligible(error) is True
    assert is_breaker_failure(error) is True


def test_local_missing_credential_is_not_fallback_eligible() -> None:
    error = GatewayError(
        category=GatewayErrorCategory.CONFIG_OR_AUTH_ERROR,
        message="Missing API credential for provider 'gemini'.",
        provider="gemini",
    )
    assert error.status_code is None
    assert is_fallback_eligible(error) is False
    assert is_breaker_failure(error) is False


@pytest.mark.parametrize("status_code", [None, 200])
def test_malformed_successful_response_is_fallback_eligible(status_code: int | None) -> None:
    error = GatewayError(
        category=GatewayErrorCategory.INVALID_PROVIDER_RESPONSE,
        message="Provider response failed structural validation.",
        provider="groq",
        status_code=status_code,
    )
    assert is_fallback_eligible(error) is True
    assert is_breaker_failure(error) is True


def test_deterministic_4xx_rejection_is_not_fallback_eligible() -> None:
    error = GatewayError(
        category=GatewayErrorCategory.INVALID_PROVIDER_RESPONSE,
        message="Provider returned HTTP 400.",
        provider="gemini",
        status_code=400,
    )
    assert is_fallback_eligible(error) is False
    assert is_breaker_failure(error) is False


def test_local_input_and_unclassified_errors_are_not_fallback_eligible() -> None:
    for category in (
        GatewayErrorCategory.CALLER_INPUT_ERROR,
        GatewayErrorCategory.UNKNOWN_PROVIDER_ERROR,
        GatewayErrorCategory.DUAL_PROVIDER_FAILURE,
    ):
        error = GatewayError(
            category=category, message="local or terminal fault", provider="gemini"
        )
        assert is_fallback_eligible(error) is False
        assert is_breaker_failure(error) is False


def test_breaker_open_error_routes_to_fallback_but_never_counts() -> None:
    error = GatewayError(
        category=GatewayErrorCategory.CIRCUIT_BREAKER_OPEN,
        message="Circuit breaker for provider 'gemini' is open; attempt skipped.",
        provider="gemini",
    )
    assert is_fallback_eligible(error) is True
    assert is_breaker_failure(error) is False


def test_non_gateway_exceptions_never_count_toward_breaker() -> None:
    assert is_breaker_failure(RuntimeError("unexpected")) is False


def test_billing_402_is_provider_unavailable_and_eligible() -> None:
    assert classify_http_error(402) is GatewayErrorCategory.PROVIDER_UNAVAILABLE
    error = GatewayError(
        category=classify_http_error(402),
        message="Provider returned HTTP 402.",
        provider="groq",
        status_code=402,
    )
    assert is_fallback_eligible(error) is True


def test_breaker_open_skips_then_fallback_still_available_to_orchestrator() -> None:
    breakers = GatewayBreakers(_gateway_config())
    _force_open(breakers, "gemini")

    with pytest.raises(GatewayError) as exc_info:
        breakers.call("gemini", lambda: "primary-should-not-run")
    assert exc_info.value.category is GatewayErrorCategory.CIRCUIT_BREAKER_OPEN
    assert is_fallback_eligible(exc_info.value) is True
    assert breakers.call("groq", lambda: "fallback-served") == "fallback-served"
