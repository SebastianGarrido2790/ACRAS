"""Gateway orchestration entry point: bounded primary -> fallback routing (Stage 6).

Governed by:
    ADR-006 / ADR-009 / ADR-034: Custom gateway; Gemini primary; Groq-direct fallback.
    GW-FR-04 / GW-FR-07 / GW-FR-10 / GW-FR-12 / GW-FR-13: Typed normalized success,
        structured redacted events for attempts and outcomes, injectable transport,
        immutable EvidenceBundle v1 and deterministic tiers.
    RES-FR-01/02/03/11/12: At most one primary and one fallback attempt per call;
        approved timeouts; zero same-provider retries; one sanitized dual-failure
        result with causal context; routing and breaker transitions emit events.
    D3-03 (Option B) / D3-05 / D3-06: Bounded attempt policy, sanitized causal
        context, deterministic mock-transport testing.

Boundaries (INV-1, INV-6): this module imports no Tier 1/2 code and writes no
EvidenceBundle state; gateway output never feeds deterministic calculations.
Raw provider or transport exceptions never cross the public boundary: callers
receive ``GatewayResult`` or a normalized ``GatewayError``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from contextvars import ContextVar

import httpx
import pybreaker

from src.gateway.config import GatewayConfig, ProviderSettings, calculate_cost_usd
from src.gateway.contracts import (
    GatewayError,
    GatewayErrorCategory,
    GatewayRequest,
    GatewayResult,
)
from src.gateway.events import (
    build_attempt_event,
    build_breaker_event,
    build_error_event,
    build_result_event,
    emit_event,
)
from src.gateway.providers.gemini import invoke_gemini
from src.gateway.providers.groq import invoke_groq
from src.gateway.resilience import GatewayBreakers, is_fallback_eligible

_CORRELATION_ID: ContextVar[str] = ContextVar("gateway_correlation_id", default="unknown")

_PROVIDER_INVOKERS: dict[str, Callable[..., GatewayResult]] = {
    "gemini": invoke_gemini,
    "groq": invoke_groq,
}


def _normalize_state(state: str) -> str:
    """Normalize pybreaker state names to the event vocabulary ('half_open')."""
    return state.replace("-", "_")


def _models_by_provider(config: GatewayConfig) -> dict[str, str]:
    return {
        config.primary.provider: config.primary.model,
        config.fallback.provider: config.fallback.model,
    }


class BreakerTransitionListener(pybreaker.CircuitBreakerListener):
    """Emit redacted breaker_transition events tagged with the invoking request."""

    def __init__(self, logger: logging.Logger, models_by_provider: Mapping[str, str]) -> None:
        self._logger = logger
        self._models_by_provider = dict(models_by_provider)

    def state_change(
        self,
        cb: pybreaker.CircuitBreaker,
        old_state: pybreaker.CircuitBreakerState | None,
        new_state: pybreaker.CircuitBreakerState,
    ) -> None:
        provider = (cb.name or "unknown").removeprefix("gateway-")
        emit_event(
            self._logger,
            build_breaker_event(
                correlation_id=_CORRELATION_ID.get(),
                provider=provider,
                model=self._models_by_provider.get(provider, "unknown"),
                breaker_state=_normalize_state(new_state.name),
                previous_state=_normalize_state(old_state.name)
                if old_state is not None
                else None,
            ),
        )


class GatewayService:
    """Bounded primary -> fallback orchestrator over the approved gateway contracts.

    One gateway call produces at most two provider attempts: one primary and, on
    an approved fallback-eligible failure or open breaker, one fallback. There
    are no same-provider retries and no recursive fallback (RES-FR-01–03).

    Operational notes:
        - Breaker state is process-local (Stage 5 boundary); pass an injected
          ``breakers`` instance only to share state across services in-process.
        - The default logger is ``logging.getLogger(__name__)``; events are
          emitted through the Stage 4 versioned schema and never include prompt
          or completion content, credentials, or raw provider bodies.
    """

    def __init__(
        self,
        config: GatewayConfig,
        *,
        client: httpx.Client | None = None,
        logger: logging.Logger | None = None,
        breakers: GatewayBreakers | None = None,
    ) -> None:
        for settings in (config.primary, config.fallback):
            if settings.provider not in _PROVIDER_INVOKERS:
                raise ValueError(
                    f"Unknown provider '{settings.provider}' in gateway configuration; "
                    f"registered adapters: {sorted(_PROVIDER_INVOKERS)}."
                )
        if config.max_attempts != 2 or config.retries_per_provider != 0:
            raise ValueError(
                "Phase 3 implements exactly one primary plus one fallback attempt with "
                "zero same-provider retries; changing max_attempts or retries_per_provider "
                "requires a new approved decision (RES-FR-01–03)."
            )
        self._config = config
        self._client = client if client is not None else httpx.Client()
        self._logger = logger if logger is not None else logging.getLogger(__name__)
        self._breakers = (
            breakers
            if breakers is not None
            else GatewayBreakers(
                config,
                listener=BreakerTransitionListener(self._logger, _models_by_provider(config)),
            )
        )

    def complete(self, request: GatewayRequest) -> GatewayResult:
        """Route one request: primary once, then fallback at most once.

        Returns:
            GatewayResult from whichever provider served the request, with
            ``fallback_used`` reflecting the actual route taken.

        Raises:
            GatewayError: The primary's normalized error when it is not
                fallback-eligible (fail-fast classes such as local
                configuration/credential faults and deterministic request
                rejections), or a normalized DUAL_PROVIDER_FAILURE carrying
                sanitized causal categories when both legs fail or are skipped.
        """
        token = _CORRELATION_ID.set(request.correlation_id)
        try:
            primary_error: GatewayError
            try:
                return self._attempt(
                    request,
                    settings=self._config.primary,
                    attempt=1,
                    fallback_used=False,
                )
            except GatewayError as exc:
                primary_error = exc
                if not is_fallback_eligible(exc):
                    raise

            try:
                return self._attempt(
                    request,
                    settings=self._config.fallback,
                    attempt=2,
                    fallback_used=True,
                )
            except GatewayError as fallback_error:
                dual = GatewayError(
                    category=GatewayErrorCategory.DUAL_PROVIDER_FAILURE,
                    message=(
                        "Primary and fallback attempts both failed "
                        f"(primary={primary_error.category.value}, "
                        f"fallback={fallback_error.category.value})."
                    ),
                    correlation_id=request.correlation_id,
                    cause_error=fallback_error,
                )
                emit_event(
                    self._logger,
                    build_error_event(
                        dual,
                        provider=self._config.fallback.provider,
                        model=self._config.fallback.model,
                        attempt=2,
                        fallback_used=True,
                        breaker_state=self._breaker_state_for_events(
                            self._config.fallback.provider
                        ),
                    ),
                )
                raise dual from fallback_error
        finally:
            _CORRELATION_ID.reset(token)

    def _attempt(
        self,
        request: GatewayRequest,
        *,
        settings: ProviderSettings,
        attempt: int,
        fallback_used: bool,
    ) -> GatewayResult:
        invoker = _PROVIDER_INVOKERS[settings.provider]

        def guarded() -> GatewayResult:
            emit_event(
                self._logger,
                build_attempt_event(
                    correlation_id=request.correlation_id,
                    provider=settings.provider,
                    model=settings.model,
                    attempt=attempt,
                    fallback_used=fallback_used,
                ),
            )
            return invoker(
                self._client,
                settings,
                request,
                user_agent=self._config.default_user_agent,
            )

        try:
            result = self._breakers.call(
                settings.provider, guarded, correlation_id=request.correlation_id
            )
        except GatewayError as error:
            emit_event(
                self._logger,
                build_error_event(
                    error,
                    provider=settings.provider,
                    model=settings.model,
                    attempt=attempt,
                    fallback_used=fallback_used,
                    breaker_state=self._breaker_state_for_events(settings.provider),
                ),
            )
            raise
        cost = calculate_cost_usd(result.model, result.usage, self._config.cost_rates)
        if cost is not None:
            result = result.model_copy(update={"cost_usd": cost})
        emit_event(
            self._logger,
            build_result_event(result, attempt=attempt, cost_rates=self._config.cost_rates),
        )
        return result

    def _breaker_state_for_events(self, provider: str) -> str | None:
        try:
            return _normalize_state(self._breakers.state_of(provider))
        except ValueError:
            return None
