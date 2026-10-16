"""Thin Gemini primary-provider adapter (Stage 2 / GW-T05).

Governed by:
    D3-01 (Option B): Thin adapter over shared injectable transport; zero
        adapter-level retries; OpenAI-compatible request/response mapping.
    D3-05: Fail-closed parsing; sanitized normalized errors.
    GW-FR-04 / GW-FR-05 / GW-FR-06 / GW-FR-12: Normalized success, malformed
        responses fail, bounded taxonomy, mockable transport.
    Qualification: `gemini-2.5-flash` on Google's OpenAI-compatible endpoint
        (D3-02, 2026-10-12).
"""

from __future__ import annotations

import httpx

from src.gateway.config import ProviderSettings, resolve_api_key
from src.gateway.contracts import GatewayRequest, GatewayResult
from src.gateway.providers.base import (
    AdapterContext,
    build_chat_payload,
    parse_chat_response,
    post_chat_completion,
)


def build_context(
    settings: ProviderSettings,
    request: GatewayRequest,
    *,
    user_agent: str,
) -> AdapterContext:
    """Bind provider settings, secret, and request correlation into one context."""
    return AdapterContext(
        provider=settings.provider,
        model=settings.model,
        base_url=settings.base_url,
        api_key=resolve_api_key(settings.provider),
        timeout_s=settings.timeout_s,
        user_agent=user_agent,
        correlation_id=request.correlation_id,
    )


def invoke_gemini(
    client: httpx.Client,
    settings: ProviderSettings,
    request: GatewayRequest,
    *,
    user_agent: str,
) -> GatewayResult:
    """Execute one bounded Gemini attempt with zero retries.

    Args:
        client: Injected shared httpx transport (mockable in tests).
        settings: Validated non-secret Gemini provider settings.
        request: Provider-neutral gateway request.
        user_agent: Browser-style User-Agent header value.

    Returns:
        Normalized GatewayResult on success.

    Raises:
        GatewayError: Normalized failure in every non-success case.
    """
    context = build_context(settings, request, user_agent=user_agent)
    payload = build_chat_payload(request, context.model)
    body, latency_ms = post_chat_completion(client, payload, context=context)
    return parse_chat_response(
        body,
        context=context,
        request=request,
        latency_ms=latency_ms,
        fallback_used=False,
    )
