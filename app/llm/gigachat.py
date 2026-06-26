import uuid

import httpx


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
        self._access_token: str | None = None

    async def _get_access_token(self) -> str:
        if self._access_token is not None:
            return self._access_token

        async with httpx.AsyncClient(
            verify=self.verify_ssl,
            timeout=self.timeout_seconds,
        ) as client:
            response = await client.post(
                self.oauth_url,
                headers={
                    "Authorization": f"Basic {self.api_key}",
                    "RqUID": str(uuid.uuid4()),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"scope": self.scope},
            )
            response.raise_for_status()
            self._access_token = response.json()["access_token"]
            return self._access_token

    async def complete(self, prompt: str) -> str:
        access_token = await self._get_access_token()

        async with httpx.AsyncClient(
            verify=self.verify_ssl,
            timeout=self.timeout_seconds,
        ) as client:
            response = await client.post(
                f"{self.api_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
