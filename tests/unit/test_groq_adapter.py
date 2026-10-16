"""Unit tests and falsification for the Groq fallback adapter (Stage 3 / GW-T06).

Governed by:
    D3-01 (Option B): Thin adapter over shared injectable transport; zero retries.
    ADR-034: Groq-direct `openai/gpt-oss-20b` pin.
    D3-05: Fail-closed parsing; sanitized normalized errors.
    GW-FR-02 / GW-FR-03 / GW-FR-04 / GW-FR-11 / GW-FR-12: Pinned endpoint,
        model, env key, injected transport, tested User-Agent.
"""

from __future__ import annotations

import json

import httpx
import pytest

from src.gateway.config import ProviderSettings
from src.gateway.contracts import (
    GatewayError,
    GatewayErrorCategory,
    GatewayMessage,
    GatewayMessageRole,
    GatewayRequest,
)
from src.gateway.providers.groq import invoke_groq

GROQ_SETTINGS = ProviderSettings(
    provider="groq",
    model="openai/gpt-oss-20b",
    base_url="https://api.groq.com/openai/v1",
    timeout_s=20.0,
)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ACRAS/1.0"

SUCCESS_BODY = {
    "id": "chatcmpl-groq-001",
    "object": "chat.completion",
    "created": 1729000100,
    "model": "openai/gpt-oss-20b",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Fallback assessment ready."},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 38, "completion_tokens": 9, "total_tokens": 47},
}


def _make_request() -> GatewayRequest:
    return GatewayRequest(
        correlation_id="corr-grq-001",
        messages=[GatewayMessage(role=GatewayMessageRole.USER, content="Assess SME risk.")],
        max_tokens=64,
    )


def _client_with_handler(handler: object) -> httpx.Client:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return httpx.Client(transport=transport)


def test_groq_adapter_success_marks_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mocked success parses with pinned model and fallback_used=True."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == USER_AGENT
        assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
        payload = json.loads(request.content.decode())
        assert payload["model"] == "openai/gpt-oss-20b"
        assert "Authorization" in request.headers
        return httpx.Response(200, json=SUCCESS_BODY)

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_groq_key")
    client = _client_with_handler(handler)
    try:
        result = invoke_groq(client, GROQ_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert result.correlation_id == "corr-grq-001"
    assert result.content == "Fallback assessment ready."
    assert result.provider == "groq"
    assert result.model == "openai/gpt-oss-20b"
    assert result.fallback_used is True
    assert result.latency_ms >= 0.0
    assert result.usage is not None
    assert result.usage.total_tokens == 47
    assert result.cost_usd is None


def test_groq_adapter_missing_auth_fails_controlled(monkeypatch: pytest.MonkeyPatch) -> None:
    """[Stage 3 Falsification] Missing GROQ_API_KEY fails before any network call."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=SUCCESS_BODY)

    client = _client_with_handler(handler)
    try:
        with pytest.raises(GatewayError) as exc_info:
            invoke_groq(client, GROQ_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert exc_info.value.category == GatewayErrorCategory.CONFIG_OR_AUTH_ERROR
    assert "GROQ_API_KEY" in str(exc_info.value)
    assert calls == []


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, GatewayErrorCategory.INVALID_PROVIDER_RESPONSE),
        (401, GatewayErrorCategory.CONFIG_OR_AUTH_ERROR),
        (403, GatewayErrorCategory.CONFIG_OR_AUTH_ERROR),
        (429, GatewayErrorCategory.RATE_LIMIT_ERROR),
        (500, GatewayErrorCategory.PROVIDER_UNAVAILABLE),
        (503, GatewayErrorCategory.PROVIDER_UNAVAILABLE),
    ],
)
def test_groq_adapter_http_status_mapping(
    monkeypatch: pytest.MonkeyPatch, status: int, expected: GatewayErrorCategory
) -> None:
    """Representative HTTP statuses map to the approved error categories."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"message": "provider says no"}})

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_groq_key")
    client = _client_with_handler(handler)
    try:
        with pytest.raises(GatewayError) as exc_info:
            invoke_groq(client, GROQ_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert exc_info.value.category == expected
    assert exc_info.value.status_code == status


def test_groq_adapter_balance_rejection_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """[Stage 3 Falsification] Balance/billing 403 classifies as provider-side, not auth."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "code": 403,
                "reason": "NOT_ENOUGH_BALANCE",
                "message": "not enough balance",
            },
        )

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_groq_key")
    client = _client_with_handler(handler)
    try:
        with pytest.raises(GatewayError) as exc_info:
            invoke_groq(client, GROQ_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert exc_info.value.category == GatewayErrorCategory.PROVIDER_UNAVAILABLE


def test_groq_adapter_timeout_and_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Timeout and connection failures normalize with exactly one attempt."""

    calls: list[httpx.Request] = []

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ConnectTimeout("simulated timeout")

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_groq_key")
    client = _client_with_handler(timeout_handler)
    try:
        with pytest.raises(GatewayError) as exc_info:
            invoke_groq(client, GROQ_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert exc_info.value.category == GatewayErrorCategory.TIMEOUT_ERROR
    assert len(calls) == 1

    def conn_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated refused")

    client2 = _client_with_handler(conn_handler)
    try:
        with pytest.raises(GatewayError) as exc_info2:
            invoke_groq(client2, GROQ_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client2.close()
    assert exc_info2.value.category == GatewayErrorCategory.CONNECTION_ERROR


def test_groq_adapter_malformed_completion_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """[Stage 3 Falsification] Malformed completion fails closed, never success."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant"}}]})

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_groq_key")
    client = _client_with_handler(handler)
    try:
        with pytest.raises(GatewayError) as exc_info:
            invoke_groq(client, GROQ_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert exc_info.value.category == GatewayErrorCategory.INVALID_PROVIDER_RESPONSE


def test_groq_adapter_no_usage_stays_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """[Stage 3 Falsification] Missing usage metadata stays unknown, never zero."""
    body = dict(SUCCESS_BODY)
    body.pop("usage")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_groq_key")
    client = _client_with_handler(handler)
    try:
        result = invoke_groq(client, GROQ_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert result.usage is None
    assert result.cost_usd is None


def test_groq_adapter_no_secret_in_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """[Stage 3 Falsification] Live-shaped secrets never leak into normalized errors."""
    sentinel = "SECRET_SENTINEL_GSK_KEY_NEVER_LOG"
    monkeypatch.setenv("GROQ_API_KEY", sentinel)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = _client_with_handler(handler)
    try:
        with pytest.raises(GatewayError) as exc_info:
            invoke_groq(client, GROQ_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert sentinel not in str(exc_info.value)
    assert sentinel not in str(exc_info.value.to_dict())
