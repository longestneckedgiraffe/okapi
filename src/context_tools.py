from __future__ import annotations

import json
from typing import Any
from datetime import datetime, timezone

import discord

from context_manager import ContextManager, ConversationMessage


class ContextTools:
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "fetch_recent_messages",
                    "description": "Fetch recent messages from the conversation history to understand context",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Number of recent messages to fetch (max 20)",
                                "minimum": 1,
                                "maximum": 20,
                                "default": 10,
                            },
                            "include_bot_messages": {
                                "type": "boolean",
                                "description": "Whether to include bot's own messages",
                                "default": True,
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_conversation_history",
                    "description": "Search through conversation history for messages containing specific keywords or from specific users",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Keywords to search for in message content",
                            },
                            "author_name": {
                                "type": "string",
                                "description": "Filter messages by specific author name",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of messages to return",
                                "minimum": 1,
                                "maximum": 15,
                                "default": 5,
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_conversation_summary",
                    "description": "Get a summary of the current conversation including message counts and activity",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
        ]

    async def execute_tool(
        self,
        tool_name: str,
        channel_id: str,
        arguments: dict[str, Any],
        discord_channel: discord.TextChannel = None,
    ) -> str:
        try:
            if tool_name == "fetch_recent_messages":
                return await self._fetch_recent_messages(
                    channel_id, arguments, discord_channel
                )
            elif tool_name == "search_conversation_history":
                return await self._search_conversation_history(channel_id, arguments)
            elif tool_name == "get_conversation_summary":
                return await self._get_conversation_summary(channel_id)
            else:
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    async def _fetch_recent_messages(
        self,
        channel_id: str,
        arguments: dict[str, Any],
        discord_channel: discord.TextChannel = None,
    ) -> str:
        limit = min(arguments.get("limit", 10), 20)
        include_bot_messages = arguments.get("include_bot_messages", True)

        context_messages = await self.context_manager.get_recent_messages(
            channel_id, limit * 2
        )

        if len(context_messages) < limit and discord_channel:
            try:
                discord_messages = []
                async for msg in discord_channel.history(limit=limit * 2):
                    if not include_bot_messages and msg.author.bot:
                        continue

                    conv_msg = ConversationMessage(
                        id=str(msg.id),
                        author_id=str(msg.author.id),
                        author_name=msg.author.display_name,
                        content=msg.content,
                        timestamp=msg.created_at.timestamp(),
                        role="assistant" if msg.author.bot else "user",
                        is_bot=msg.author.bot,
                        token_count=self.context_manager._estimate_tokens(msg.content),
                    )
                    discord_messages.append(conv_msg)

                all_messages = {}
                for msg in context_messages + discord_messages:
                    all_messages[msg.id] = msg

                context_messages = sorted(
                    all_messages.values(), key=lambda x: x.timestamp
                )[-limit:]

            except Exception as e:
                print(f"Error fetching Discord messages: {e}")

        if not include_bot_messages:
            context_messages = [msg for msg in context_messages if not msg.is_bot]

        if not context_messages:
            return "No recent messages found in conversation history."

        formatted_messages = []
        for msg in context_messages[-limit:]:
            timestamp = datetime.fromtimestamp(msg.timestamp, tz=timezone.utc)
            formatted_messages.append(
                f"[{timestamp.strftime('%H:%M')}] {msg.author_name}: {msg.content}"
            )

        return "Recent conversation history:\n" + "\n".join(formatted_messages)

    async def _search_conversation_history(
        self, channel_id: str, arguments: dict[str, Any]
    ) -> str:
        keywords = arguments.get("keywords", [])
        author_name = arguments.get("author_name", "").lower()
        limit = min(arguments.get("limit", 5), 15)

        context = await self.context_manager.get_conversation_context(
            channel_id, create_if_missing=False
        )
        if not context or not context.messages:
            return "No conversation history found."

        matching_messages = []

        for msg in context.messages:
            matches = True

            if author_name and author_name not in msg.author_name.lower():
                matches = False

            if keywords and matches:
                content_lower = msg.content.lower()
                if not any(keyword.lower() in content_lower for keyword in keywords):
                    matches = False

            if matches:
                matching_messages.append(msg)

        if not matching_messages:
            search_desc = []
            if keywords:
                search_desc.append(f"keywords: {', '.join(keywords)}")
            if author_name:
                search_desc.append(f"author: {author_name}")

            return f"No messages found matching {', '.join(search_desc)}."

        matching_messages.sort(
            key=lambda x: (x.relevance_score, x.timestamp), reverse=True
        )
        top_messages = matching_messages[:limit]

        formatted_messages = []
        for msg in top_messages:
            timestamp = datetime.fromtimestamp(msg.timestamp, tz=timezone.utc)
            formatted_messages.append(
                f"[{timestamp.strftime('%Y-%m-%d %H:%M')}] {msg.author_name}: {msg.content}"
            )

        search_info = []
        if keywords:
            search_info.append(f"keywords: {', '.join(keywords)}")
        if author_name:
            search_info.append(f"author: {author_name}")

        return (
            f"Found {len(matching_messages)} messages matching {', '.join(search_info)}:\n\n"
            + "\n".join(formatted_messages)
        )

    async def _get_conversation_summary(self, channel_id: str) -> str:
        summary = await self.context_manager.get_conversation_summary(channel_id)
        return f"Conversation Summary:\n{summary}"


def format_tools_for_mistral(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return tools


async def process_tool_calls(
    tool_calls: list[dict[str, Any]],
    context_tools: ContextTools,
    channel_id: str,
    discord_channel: discord.TextChannel = None,
) -> list[dict[str, Any]]:
    tool_results = []

    for tool_call in tool_calls:
        try:
            function_name = tool_call["function"]["name"]
            arguments_raw = tool_call["function"].get("arguments", {})

            if isinstance(arguments_raw, dict):
                arguments = arguments_raw
            elif isinstance(arguments_raw, str):
                if not arguments_raw.strip():
                    arguments = {}
                else:
                    try:
                        arguments = json.loads(arguments_raw)
                    except json.JSONDecodeError:
                        arguments = {}
            else:
                arguments = {}

            result = await context_tools.execute_tool(
                function_name, channel_id, arguments, discord_channel
            )

            tool_results.append(
                {
                    "tool_call_id": tool_call.get("id", f"call_{len(tool_results)}"),
                    "role": "tool",
                    "name": function_name,
                    "content": result,
                }
            )

        except Exception as e:
            tool_results.append(
                {
                    "tool_call_id": tool_call.get("id", f"call_{len(tool_results)}"),
                    "role": "tool",
                    "name": tool_call.get("function", {}).get("name", "unknown"),
                    "content": f"Error: {str(e)}",
                }
            )

    return tool_results
