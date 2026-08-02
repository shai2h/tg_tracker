import time
import uuid

import httpx

from app.core.config import Settings
from app.llm.exceptions import RetryableLLMError


class GigaChatProvider:
    def __init__(
        self,
        api_key: str,
        scope: str,
        oauth_url: str,
        api_base_url: str,
        model: str,
        verify_ssl: bool,
        timeout_seconds: int,
        max_tokens: int,
        temperature: float,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.scope = scope
        self.oauth_url = oauth_url
        self.api_base_url = api_base_url
        self.model = model
        self.verify_ssl = verify_ssl
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._max_retries = max_retries
        self._access_token: str | None = None
        self._access_token_expires_at: float | None = None
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                verify=self.verify_ssl,
                timeout=self.timeout_seconds,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _raise_for_status(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                raise RetryableLLMError("provider http 5xx") from exc
            raise

    async def _post(self, url: str, **kwargs) -> httpx.Response:
        client = self._get_client()
        try:
            response = await client.post(url, **kwargs)
        except httpx.RequestError as exc:
            raise RetryableLLMError("provider request failed") from exc

        self._raise_for_status(response)
        return response

    async def _get_access_token(self) -> str:
        if (
            self._access_token is not None
            and self._access_token_expires_at is not None
            and time.monotonic() < self._access_token_expires_at
        ):
            return self._access_token

        response = await self._post(
            self.oauth_url,
            headers={
                "Authorization": f"Basic {self.api_key}",
                "RqUID": str(uuid.uuid4()),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"scope": self.scope},
        )
        payload = response.json()
        expires_in = payload.get("expires_in", 1800)
        self._access_token = payload["access_token"]
        self._access_token_expires_at = time.monotonic() + max(expires_in - 60, 0)
        return self._access_token

    async def complete(
        self,
        prompt: str,
        response_format: dict[str, object] | None = None,
    ) -> str:
        for attempt in range(self._max_retries):
            try:
                return await self._do_complete(prompt, response_format)
            except RetryableLLMError:
                if attempt == self._max_retries - 1:
                    raise
        raise AssertionError("unreachable")

    async def _do_complete(
        self,
        prompt: str,
        response_format: dict[str, object] | None = None,
    ) -> str:
        access_token = await self._get_access_token()
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        response = await self._post(
            f"{self.api_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        return response.json()["choices"][0]["message"]["content"]


def build_gigachat_provider(settings: Settings) -> GigaChatProvider:
    return GigaChatProvider(
        api_key=settings.GIGACHAT_AUTH_KEY,
        scope=settings.GIGACHAT_SCOPE,
        oauth_url=settings.GIGACHAT_OAUTH_URL,
        api_base_url=settings.GIGACHAT_API_BASE_URL,
        model=settings.GIGACHAT_MODEL,
        verify_ssl=settings.GIGACHAT_VERIFY_SSL,
        timeout_seconds=settings.GIGACHAT_TIMEOUT_SECONDS,
        max_tokens=settings.GIGACHAT_MAX_TOKENS,
        temperature=settings.GIGACHAT_TEMPERATURE,
    )
