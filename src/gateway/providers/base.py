"""Shared transport and error-normalization primitives for provider adapters.

Governed by:
    D3-01 (Option B): One injectable transport; explicit timeouts and retry
        ownership; no hidden adapter-level retries.
    D3-05: Provider failures normalized into a bounded typed taxonomy using
        status plus machine-readable reason, never status alone.
    GW-FR-04 / GW-FR-05 / GW-FR-06 / GW-FR-12: Normalized results, fail-closed
        parsing, bounded errors, mockable transport with no live CI dependency.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from src.gateway.contracts import (
    GatewayError,
    GatewayErrorCategory,
    GatewayRequest,
    GatewayResult,
    ProviderUsage,
)

RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class AdapterContext:
    """Bounded execution context for a single provider attempt."""

    provider: str
    model: str
    base_url: str
    api_key: str
    timeout_s: float
    user_agent: str
    correlation_id: str


def build_headers(api_key: str, user_agent: str) -> dict[str, str]:
    """Build the sanitized header set for a provider request.

    The browser-style User-Agent is required: several provider edges
    (Cloudflare-fronted APIs) reject default HTTP-client fingerprints
    independent of credential validity (qualification evidence D3-02).
    """
    return {
        "Authorization": "Bearer REDACTED",
        "Content-Type": "application/json",
        "User-Agent": user_agent,
    }


def _auth_headers(api_key: str, user_agent: str) -> dict[str, str]:
    """Build the real wire headers (Authorization carries the live key)."""
    headers = build_headers(api_key, user_agent)
    headers["Authorization"] = f"Bearer {api_key}"
    return headers


def classify_http_error(status_code: int, reason: str | None = None) -> GatewayErrorCategory:
    """Classify an HTTP failure using status plus machine-readable reason.

    Args:
        status_code: HTTP response status.
        reason: Optional provider-supplied machine-readable reason string.

    Returns:
        The matching GatewayErrorCategory. Balance/billing rejections are
        provider-side availability faults, never authentication errors.
    """
    if status_code == 429:
        return GatewayErrorCategory.RATE_LIMIT_ERROR
    if status_code in (401, 403):
        normalized_reason = (reason or "").upper()
        if "BALANCE" in normalized_reason or "BILLING" in normalized_reason:
            return GatewayErrorCategory.PROVIDER_UNAVAILABLE
        return GatewayErrorCategory.CONFIG_OR_AUTH_ERROR
    if status_code in (500, 502, 503, 504, 408, 425):
        return GatewayErrorCategory.PROVIDER_UNAVAILABLE
    if 400 <= status_code < 500:
        return GatewayErrorCategory.INVALID_PROVIDER_RESPONSE
    return GatewayErrorCategory.UNKNOWN_PROVIDER_ERROR


def normalize_error(
    exc: BaseException,
    *,
    context: AdapterContext,
) -> GatewayError:
    """Normalize any transport or protocol failure into a GatewayError.

    Never includes request bodies, credentials, or raw provider payloads.
    """
    if isinstance(exc, httpx.TimeoutException):
        return GatewayError(
            category=GatewayErrorCategory.TIMEOUT_ERROR,
            message=f"Provider request timed out after {context.timeout_s}s.",
            correlation_id=context.correlation_id,
            provider=context.provider,
        )
    if isinstance(exc, httpx.ConnectError):
        return GatewayError(
            category=GatewayErrorCategory.CONNECTION_ERROR,
            message="Could not establish a connection to the provider endpoint.",
            correlation_id=context.correlation_id,
            provider=context.provider,
        )
    if isinstance(exc, httpx.HTTPError):
        return GatewayError(
            category=GatewayErrorCategory.CONNECTION_ERROR,
            message=f"HTTP transport failure: {type(exc).__name__}.",
            correlation_id=context.correlation_id,
            provider=context.provider,
        )
    if isinstance(exc, GatewayError):
        return exc
    return GatewayError(
        category=GatewayErrorCategory.UNKNOWN_PROVIDER_ERROR,
        message=f"Unexpected adapter failure: {type(exc).__name__}.",
        correlation_id=context.correlation_id,
        provider=context.provider,
    )


def build_chat_payload(request: GatewayRequest, model: str) -> dict:
    """Serialize a GatewayRequest into an OpenAI-compatible chat payload."""
    payload: dict = {
        "model": model,
        "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
    }
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    if request.temperature != 0.0:
        payload["temperature"] = request.temperature
    return payload


def parse_chat_response(
    body: object,
    *,
    context: AdapterContext,
    request: GatewayRequest,
    latency_ms: float,
    fallback_used: bool = False,
) -> GatewayResult:
    """Validate a provider response body into a GatewayResult (fail-closed).

    Raises:
        GatewayError: INVALID_PROVIDER_RESPONSE when required structure is
            missing or malformed. Usage/cost stay None when absent.
    """
    failure = GatewayError(
        category=GatewayErrorCategory.INVALID_PROVIDER_RESPONSE,
        message="Provider response failed structural validation.",
        correlation_id=request.correlation_id,
        provider=context.provider,
    )
    if not isinstance(body, dict):
        raise failure
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise failure
    first = choices[0]
    if not isinstance(first, dict):
        raise failure
    message = first.get("message")
    if not isinstance(message, dict):
        raise failure
    content = message.get("content")
    if not isinstance(content, str) or not content:
        raise failure

    usage: ProviderUsage | None = None
    raw_usage = body.get("usage")
    if isinstance(raw_usage, dict):
        try:
            usage = ProviderUsage(
                prompt_tokens=int(raw_usage.get("prompt_tokens", 0)),
                completion_tokens=int(raw_usage.get("completion_tokens", 0)),
                total_tokens=int(
                    raw_usage.get(
                        "total_tokens",
                        int(raw_usage.get("prompt_tokens", 0))
                        + int(raw_usage.get("completion_tokens", 0)),
                    )
                ),
            )
        except (TypeError, ValueError):
            usage = None

    finish = first.get("finish_reason")
    return GatewayResult(
        correlation_id=request.correlation_id,
        content=content,
        provider=context.provider,
        model=context.model,
        fallback_used=fallback_used,
        finish_reason=str(finish) if finish is not None else None,
        latency_ms=max(0.0, float(latency_ms)),
        usage=usage,
        cost_usd=None,
    )


def post_chat_completion(
    client: httpx.Client,
    payload: dict,
    *,
    context: AdapterContext,
    path: str = "/chat/completions",
) -> tuple[dict, float]:
    """POST one chat payload with zero retries; return (parsed body, latency_ms).

    Raises:
        GatewayError: Normalized TIMEOUT/CONNECTION/HTTP-status failure.
    """
    url = context.base_url.rstrip("/") + path
    started_ns = time.perf_counter_ns()
    try:
        response = client.post(
            url,
            json=payload,
            headers=_auth_headers(context.api_key, context.user_agent),
            timeout=context.timeout_s,
        )
    except Exception as exc:
        raise normalize_error(exc, context=context) from exc
    latency_ms = (time.perf_counter_ns() - started_ns) / 1e6

    if response.status_code != 200:
        reason: str | None = None
        try:
            reason_body = response.json()
            if isinstance(reason_body, dict):
                reason = str(reason_body.get("reason") or reason_body.get("error") or "")
        except Exception:
            reason = None
        category = classify_http_error(response.status_code, reason)
        raise GatewayError(
            category=category,
            message=f"Provider returned HTTP {response.status_code}.",
            correlation_id=context.correlation_id,
            provider=context.provider,
            status_code=response.status_code,
        )
    try:
        body = response.json()
    except Exception as exc:
        raise GatewayError(
            category=GatewayErrorCategory.INVALID_PROVIDER_RESPONSE,
            message="Provider returned a non-JSON response body.",
            correlation_id=context.correlation_id,
            provider=context.provider,
            status_code=response.status_code,
        ) from exc
    return body, latency_ms
