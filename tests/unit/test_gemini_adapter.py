"""Unit tests and falsification for the Gemini primary adapter (Stage 2 / GW-T05).

Governed by:
    D3-01 (Option B): Thin adapter over shared injectable transport; zero retries.
    D3-05: Fail-closed parsing; sanitized normalized errors.
    GW-FR-04 / GW-FR-05 / GW-FR-06 / GW-FR-12: Normalized success, malformed
        responses fail, bounded taxonomy, mockable transport with no live CI.
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
from src.gateway.providers.base import build_chat_payload
from src.gateway.providers.gemini import invoke_gemini

GEMINI_SETTINGS = ProviderSettings(
    provider="gemini",
    model="gemini-2.5-flash",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    timeout_s=15.0,
)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ACRAS/1.0"

SUCCESS_BODY = {
    "id": "chatcmpl-test-001",
    "object": "chat.completion",
    "created": 1729000000,
    "model": "gemini-2.5-flash",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Risk assessment complete."},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 42, "completion_tokens": 8, "total_tokens": 50},
}


def _make_request() -> GatewayRequest:
    return GatewayRequest(
        correlation_id="corr-gem-001",
        messages=[GatewayMessage(role=GatewayMessageRole.USER, content="Assess SME risk.")],
        max_tokens=64,
    )


def _client_with_handler(handler: object) -> httpx.Client:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return httpx.Client(transport=transport)


def _success_handler(request: httpx.Request) -> httpx.Response:
    assert request.headers["User-Agent"] == USER_AGENT
    assert request.url.path.endswith("/chat/completions")
    payload = json.loads(request.content.decode())
    assert payload["model"] == "gemini-2.5-flash"
    assert payload["messages"][0]["role"] == "user"
    assert "Authorization" in request.headers
    return httpx.Response(200, json=SUCCESS_BODY)


def test_gemini_adapter_success_normalizes_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mocked success parses into a normalized GatewayResult."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    client = _client_with_handler(_success_handler)
    try:
        result = invoke_gemini(client, GEMINI_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert result.correlation_id == "corr-gem-001"
    assert result.content == "Risk assessment complete."
    assert result.provider == "gemini"
    assert result.model == "gemini-2.5-flash"
    assert result.fallback_used is False
    assert result.finish_reason == "stop"
    assert result.latency_ms >= 0.0
    assert result.usage is not None
    assert result.usage.prompt_tokens == 42
    assert result.usage.total_tokens == 50


def test_gemini_adapter_success_without_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Success without usage metadata yields usage=None (unknown stays unknown)."""
    body = dict(SUCCESS_BODY)
    body.pop("usage")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    client = _client_with_handler(handler)
    try:
        result = invoke_gemini(client, GEMINI_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert result.usage is None
    assert result.cost_usd is None


def test_gemini_adapter_timeout_normalizes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulated timeout becomes TIMEOUT_ERROR; zero retries enforced."""

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ConnectTimeout("simulated timeout")

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    client = _client_with_handler(handler)
    try:
        with pytest.raises(GatewayError) as exc_info:
            invoke_gemini(client, GEMINI_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert exc_info.value.category == GatewayErrorCategory.TIMEOUT_ERROR
    assert exc_info.value.correlation_id == "corr-gem-001"
    assert len(calls) == 1


def test_gemini_adapter_connection_error_normalizes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulated connection failure becomes CONNECTION_ERROR."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection refused")

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    client = _client_with_handler(handler)
    try:
        with pytest.raises(GatewayError) as exc_info:
            invoke_gemini(client, GEMINI_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert exc_info.value.category == GatewayErrorCategory.CONNECTION_ERROR


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (429, GatewayErrorCategory.RATE_LIMIT_ERROR),
        (500, GatewayErrorCategory.PROVIDER_UNAVAILABLE),
        (503, GatewayErrorCategory.PROVIDER_UNAVAILABLE),
        (401, GatewayErrorCategory.CONFIG_OR_AUTH_ERROR),
        (400, GatewayErrorCategory.INVALID_PROVIDER_RESPONSE),
    ],
)
def test_gemini_adapter_http_status_mapping(
    monkeypatch: pytest.MonkeyPatch, status: int, expected: GatewayErrorCategory
) -> None:
    """Representative HTTP statuses map to the approved error categories."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"message": "provider says no"}})

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    client = _client_with_handler(handler)
    try:
        with pytest.raises(GatewayError) as exc_info:
            invoke_gemini(client, GEMINI_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert exc_info.value.category == expected
    assert exc_info.value.status_code == status


def test_gemini_adapter_malformed_body_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """[Stage 2 Falsification] Malformed bodies become failures, never success."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    client = _client_with_handler(handler)
    try:
        with pytest.raises(GatewayError) as exc_info:
            invoke_gemini(client, GEMINI_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert exc_info.value.category == GatewayErrorCategory.INVALID_PROVIDER_RESPONSE


def test_gemini_adapter_non_json_body_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """[Stage 2 Falsification] Non-JSON 200 bodies fail closed."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"this is not json {{{")

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    client = _client_with_handler(handler)
    try:
        with pytest.raises(GatewayError) as exc_info:
            invoke_gemini(client, GEMINI_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert exc_info.value.category == GatewayErrorCategory.INVALID_PROVIDER_RESPONSE


def test_gemini_adapter_missing_content_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """[Stage 2 Falsification] Empty completion content fails closed."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = dict(SUCCESS_BODY)
        body["choices"] = [{"message": {"role": "assistant", "content": ""}}]
        return httpx.Response(200, json=body)

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    client = _client_with_handler(handler)
    try:
        with pytest.raises(GatewayError) as exc_info:
            invoke_gemini(client, GEMINI_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert exc_info.value.category == GatewayErrorCategory.INVALID_PROVIDER_RESPONSE


def test_gemini_adapter_no_secret_in_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """[Stage 2 Falsification] Live-shaped secrets never leak into normalized errors."""
    sentinel = "SECRET_SENTINEL_GEMINI_KEY_NEVER_LOG"
    monkeypatch.setenv("GEMINI_API_KEY", sentinel)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = _client_with_handler(handler)
    try:
        with pytest.raises(GatewayError) as exc_info:
            invoke_gemini(client, GEMINI_SETTINGS, _make_request(), user_agent=USER_AGENT)
    finally:
        client.close()
    assert sentinel not in str(exc_info.value)
    assert sentinel not in str(exc_info.value.to_dict())


def test_build_chat_payload_json_mode_forwards_response_format() -> None:
    """json_mode=True emits response_format json_object on the wire."""
    request = GatewayRequest(
        correlation_id="corr-json-001",
        messages=[GatewayMessage(role=GatewayMessageRole.USER, content="Return JSON.")],
        max_tokens=64,
        json_mode=True,
    )
    payload = build_chat_payload(request, "gemini-2.5-flash")
    assert payload["response_format"] == {"type": "json_object"}


def test_build_chat_payload_json_mode_off_omits_response_format() -> None:
    """json_mode defaults to False, so no response_format is added."""
    request = GatewayRequest(
        correlation_id="corr-json-002",
        messages=[GatewayMessage(role=GatewayMessageRole.USER, content="Return JSON.")],
    )
    payload = build_chat_payload(request, "gemini-2.5-flash")
    assert "response_format" not in payload
