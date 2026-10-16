"""Thin Groq fallback-provider adapter (Stage 3 / GW-T06).

Governed by:
    D3-01 (Option B): Thin adapter over shared injectable transport; zero
        adapter-level retries; OpenAI-compatible request/response mapping.
    ADR-034: Groq Cloud direct fallback pinned as `openai/gpt-oss-20b`.
    D3-05: Fail-closed parsing; sanitized normalized errors.
    GW-FR-02 / GW-FR-03 / GW-FR-04 / GW-FR-11 / GW-FR-12: Pinned endpoint,
        model, env key, injected transport, tested User-Agent.
    Qualification: `openai/gpt-oss-20b` on `https://api.groq.com/openai/v1`
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


def invoke_groq(
    client: httpx.Client,
    settings: ProviderSettings,
    request: GatewayRequest,
    *,
    user_agent: str,
) -> GatewayResult:
    """Execute one bounded Groq fallback attempt with zero retries.

    Args:
        client: Injected shared httpx transport (mockable in tests).
        settings: Validated non-secret Groq provider settings (pinned model).
        request: Provider-neutral gateway request.
        user_agent: Browser-style User-Agent header value (required).

    Returns:
        Normalized GatewayResult on success (fallback_used=True).

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
        fallback_used=True,
    )
