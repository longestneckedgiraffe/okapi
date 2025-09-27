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
        messages: list[dict[str, str]] = None,
        user_message: str = None,
        system_prompt: str = "You're a helpful assistant named Okapi. You can access conversation history using tools when needed to provide context-aware responses.",
        tools: list[dict[str, Any]] = None,
        tool_choice: str = "auto",
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("MISTRAL_API_KEY is not set")

        if messages is None:
            if user_message is None:
                raise ValueError("Either messages or user_message must be provided")
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
        else:
            has_system = any(msg.get("role") == "system" for msg in messages)
            if not has_system:
                messages = [{"role": "system", "content": system_prompt}] + messages

        timeout = aiohttp.ClientTimeout(total=60)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "temperature": 0.2,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                self.api_url, headers=headers, json=payload
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise RuntimeError(f"HTTP {resp.status}: {text}")
                return await resp.json()

    async def create_context_aware_completion(
        self,
        conversation_messages: list[dict[str, str]],
        tools: list[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        system_prompt = (
            "You're a helpful assistant named Okapi. You have access to conversation history "
            "and can use tools to fetch additional context when needed. Be concise but informative. "
            "If you need to understand previous context or messages, use the available tools."
        )

        return await self.create_chat_completion(
            messages=conversation_messages,
            system_prompt=system_prompt,
            tools=tools,
            tool_choice="auto",
        )
