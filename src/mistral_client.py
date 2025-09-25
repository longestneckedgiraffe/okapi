from __future__ import annotations

import aiohttp
from typing import Any

from config import MISTRAL_API_KEY, MISTRAL_API_URL, MISTRAL_MODEL_ID


class MistralClient:
    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        model_id: str | None = None,
    ):
        self.api_key = api_key or MISTRAL_API_KEY
        self.api_url = api_url or MISTRAL_API_URL
        self.model_id = model_id or MISTRAL_MODEL_ID

    async def create_chat_completion(
        self,
        user_message: str,
        system_prompt: str = "You're a helpful assistant. Your name is Okapi.",
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("MISTRAL_API_KEY is not set")

        timeout = aiohttp.ClientTimeout(total=45)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.2,
        }

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                self.api_url, headers=headers, json=payload
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise RuntimeError(f"HTTP {resp.status}: {text}")
                return await resp.json()
