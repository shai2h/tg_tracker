from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.llm.exceptions import RetryableLLMError
from app.llm.gigachat import GigaChatProvider


def _provider() -> GigaChatProvider:
    return GigaChatProvider(
        api_key="key",
        scope="scope",
        oauth_url="https://example.test/oauth",
        api_base_url="https://example.test/api",
        model="GigaChat",
        verify_ssl=False,
        timeout_seconds=5,
        max_tokens=50,
        temperature=0.1,
    )


def _mock_client(provider: GigaChatProvider, post: AsyncMock) -> None:
    client = MagicMock()
    client.post = post
    provider._client = client


@pytest.mark.asyncio
async def test_complete_maps_request_error_to_retryable():
    provider = _provider()
    provider._access_token = "token"
    provider._access_token_expires_at = 10**12
    _mock_client(
        provider,
        AsyncMock(side_effect=httpx.ConnectError("connection failed")),
    )

    with pytest.raises(RetryableLLMError):
        await provider.complete("привет")


@pytest.mark.asyncio
async def test_complete_maps_http_500_to_retryable():
    provider = _provider()
    provider._access_token = "token"
    provider._access_token_expires_at = 10**12

    request = httpx.Request("POST", "https://example.test/api/chat/completions")
    response = httpx.Response(500, request=request)
    _mock_client(provider, AsyncMock(return_value=response))

    with pytest.raises(RetryableLLMError):
        await provider.complete("привет")


@pytest.mark.asyncio
async def test_complete_keeps_http_400_as_status_error():
    provider = _provider()
    provider._access_token = "token"
    provider._access_token_expires_at = 10**12

    request = httpx.Request("POST", "https://example.test/api/chat/completions")
    response = httpx.Response(400, request=request)
    _mock_client(provider, AsyncMock(return_value=response))

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await provider.complete("привет")

    assert exc_info.value.response.status_code == 400


@pytest.mark.asyncio
async def test_oauth_maps_http_500_to_retryable():
    provider = _provider()

    request = httpx.Request("POST", "https://example.test/oauth")
    response = httpx.Response(500, request=request)
    _mock_client(provider, AsyncMock(return_value=response))

    with pytest.raises(RetryableLLMError):
        await provider.complete("привет")
