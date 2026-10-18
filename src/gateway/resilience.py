"""Failure eligibility policy and per-provider circuit breakers (Stage 5 / RES-T01–T03, T05).

Governed by:
    RES-FR-03: zero same-provider retries; one bounded attempt per provider leg.
    RES-FR-04: independent breaker state per provider.
    RES-FR-05/06: 3 consecutive eligible failures per provider; 30 s open/reset
        interval; one half-open probe per provider (D3-03 approved starting values).
    RES-FR-07/08/09: explicit fallback eligibility matrix; local input,
        configuration, and missing-credential faults are never treated as
        transient provider failures.
    RES-FR-10: malformed/empty/schema-invalid responses are never success and
        route to the fallback exactly once.
    Clarification answers (approved 2026-10-12): 429 triggers immediate fallback
        with no same-provider retry; primary auth failure still attempts the
        fallback once; malformed successful responses trigger fallback once; one
        probe per provider per process; breaker state is process-local for Phase 3.

Pinned library semantics (pybreaker 1.4.1, verified 2026-10-12 against the
installed source):
    - ``fail_max`` trips at ``on_failure`` when the consecutive-failure counter
      reaches the threshold (``counter >= fail_max``).
    - The open -> half-open transition is lazy: the first call after
      ``reset_timeout`` elapses performs the transition and becomes the single
      probe; earlier calls raise ``CircuitBreakerError`` without invoking the
      provider.
    - ``CircuitBreaker.call()`` holds an internal ``RLock`` for the whole guarded
      call, so probes are serialized and at most one is in flight per process.
    - ``exclude`` marks exceptions as non-system errors: they are re-raised but
      treated as success for counter purposes, so a non-eligible outcome resets
      the consecutive-failure streak. Eligibility boundaries therefore live
      here, not in the library.
    - ``throw_new_error_on_trip=False``: the call that trips the breaker
      re-raises the original normalized error (keeping the true failure
      category for routing and events), while later calls surface as
      CIRCUIT_BREAKER_OPEN.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import pybreaker

from src.gateway.config import GatewayConfig
from src.gateway.contracts import GatewayError, GatewayErrorCategory

T = TypeVar("T")

FALLBACK_ELIGIBLE_CATEGORIES: frozenset[GatewayErrorCategory] = frozenset(
    {
        GatewayErrorCategory.TIMEOUT_ERROR,
        GatewayErrorCategory.CONNECTION_ERROR,
        GatewayErrorCategory.RATE_LIMIT_ERROR,
        GatewayErrorCategory.PROVIDER_UNAVAILABLE,
    }
)


def is_fallback_eligible(error: GatewayError) -> bool:
    """Decide whether a primary failure routes the gateway to the fallback.

    Approved matrix (do not broaden without returning to the decision workflow):
        - timeout, connection, rate-limit, provider-unavailable: eligible.
        - config_or_auth with an HTTP status: provider-side auth rejection
          (401/403 without a balance reason), eligible once per clarification
          answer 2. Without a status it is a local missing-credential or
          configuration fault and stays fail-fast (RES-FR-08).
        - invalid_provider_response with no status or a 2xx status: malformed
          successful response, eligible once per clarification answer 3. With a
          4xx status it is a deterministic request rejection (D3-05: 400 =
          unmapped pin or malformed payload) and is not eligible.
        - circuit_breaker_open: routing directive that skips the provider and
          proceeds to the fallback (RES-FR-07); it is not a provider fault.
        - caller_input_error, unknown_provider_error, dual_provider_failure:
          not eligible.
    """
    category = error.category
    if category in FALLBACK_ELIGIBLE_CATEGORIES:
        return True
    if category is GatewayErrorCategory.CIRCUIT_BREAKER_OPEN:
        return True
    if category is GatewayErrorCategory.CONFIG_OR_AUTH_ERROR:
        return error.status_code is not None
    if category is GatewayErrorCategory.INVALID_PROVIDER_RESPONSE:
        if error.status_code is None:
            return True
        return 200 <= error.status_code < 300
    return False


def is_breaker_failure(exc: BaseException) -> bool:
    """Decide whether an exception counts toward opening a provider breaker.

    Only normalized, provider-originated, fallback-eligible failures count
    (RES-FR-05: "3 consecutive eligible failures"). Caller input faults, local
    configuration/credential faults, deterministic 4xx rejections, unclassified
    faults, and the breaker-open routing directive never open a breaker.

    pybreaker receives ``not is_breaker_failure`` through ``exclude``; excluded
    exceptions are re-raised unchanged and reset the consecutive streak per
    pinned library semantics.
    """
    if not isinstance(exc, GatewayError):
        return False
    if exc.category is GatewayErrorCategory.CIRCUIT_BREAKER_OPEN:
        return False
    return is_fallback_eligible(exc)


class GatewayBreakers:
    """Independent per-provider pybreaker breakers bound to the approved policy.

    Operational boundary (clarification answer 5): breaker state is process-local
    (pybreaker ``CircuitMemoryStorage``). There is no cross-process coordination
    and at most one half-open probe per provider per process; reconsider only on
    deployment evidence. ``call`` invokes the guarded attempt exactly once and
    never retries (RES-FR-03).

    Configuration mapping: ``breaker_failure_threshold`` -> ``fail_max``,
    ``breaker_recovery_timeout_s`` -> ``reset_timeout``, and
    ``breaker_half_open_probes`` -> ``success_threshold`` (approved value 1:
    a single successful probe closes the breaker).
    """

    def __init__(
        self,
        config: GatewayConfig,
        *,
        listener: pybreaker.CircuitBreakerListener | None = None,
    ) -> None:
        providers = (config.primary.provider, config.fallback.provider)
        if providers[0] == providers[1]:
            raise ValueError(
                "primary and fallback must use distinct providers to keep breaker "
                "state independent (RES-FR-04)."
            )
        self._breakers: dict[str, pybreaker.CircuitBreaker] = {
            provider: self._build_breaker(provider, config, listener) for provider in providers
        }

    @staticmethod
    def _build_breaker(
        provider: str,
        config: GatewayConfig,
        listener: pybreaker.CircuitBreakerListener | None,
    ) -> pybreaker.CircuitBreaker:
        breaker = pybreaker.CircuitBreaker(
            fail_max=config.breaker_failure_threshold,
            reset_timeout=config.breaker_recovery_timeout_s,
            success_threshold=config.breaker_half_open_probes,
            exclude=[lambda exc: not is_breaker_failure(exc)],
            name=f"gateway-{provider}",
            throw_new_error_on_trip=False,
        )
        if listener is not None:
            breaker.add_listener(listener)
        return breaker

    @property
    def providers(self) -> tuple[str, ...]:
        """Return the registered provider identifiers."""
        return tuple(self._breakers)

    def state_of(self, provider: str) -> str:
        """Return the provider breaker state ('closed', 'open', or 'half-open')."""
        return self._breaker(provider).current_state

    def failure_count(self, provider: str) -> int:
        """Return the current consecutive eligible-failure count."""
        return self._breaker(provider).fail_counter

    def call(
        self,
        provider: str,
        attempt: Callable[[], T],
        *,
        correlation_id: str | None = None,
    ) -> T:
        """Execute one guarded provider attempt (zero retries).

        When the breaker is open, ``attempt`` is not invoked and a normalized
        CIRCUIT_BREAKER_OPEN error is raised; callers route that to the fallback
        per approved policy. Eligible failures re-raise their original
        normalized error, including the call that trips the breaker.

        Args:
            provider: Registered provider identifier.
            attempt: Zero-argument callable performing exactly one provider call.
            correlation_id: Optional correlation ID attached to the normalized
                breaker-open error.

        Returns:
            Whatever ``attempt`` returns on success.

        Raises:
            ValueError: If the provider has no registered breaker.
            GatewayError: CIRCUIT_BREAKER_OPEN when the attempt was skipped;
                otherwise the guarded attempt's own normalized error.
        """
        breaker = self._breaker(provider)
        try:
            return breaker.call(attempt)
        except pybreaker.CircuitBreakerError as exc:
            raise GatewayError(
                category=GatewayErrorCategory.CIRCUIT_BREAKER_OPEN,
                message=f"Circuit breaker for provider '{provider}' is open; attempt skipped.",
                correlation_id=correlation_id,
                provider=provider,
                cause_error=exc,
            ) from exc

    def _breaker(self, provider: str) -> pybreaker.CircuitBreaker:
        try:
            return self._breakers[provider]
        except KeyError:
            raise ValueError(f"No breaker registered for provider '{provider}'.") from None
