from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import discord


@dataclass
class ConversationMessage:
    id: str
    author_id: str
    author_name: str
    content: str
    timestamp: float
    role: str
    is_bot: bool
    relevance_score: float = 1.0
    token_count: int = 0

    def to_mistral_message(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationMessage:
        return cls(**data)


@dataclass
class ConversationContext:
    channel_id: str
    messages: list[ConversationMessage]
    created_at: float
    last_activity: float
    total_tokens: int = 0
    conversation_summary: str = ""
    topic_keywords: list[str] = None

    def __post_init__(self):
        if self.topic_keywords is None:
            self.topic_keywords = []

    def add_message(self, message: ConversationMessage) -> None:
        self.messages.append(message)
        self.last_activity = time.time()
        self.total_tokens += message.token_count
        self._update_relevance_scores()

    def _update_relevance_scores(self) -> None:
        current_time = time.time()

        for message in self.messages:
            time_diff = current_time - message.timestamp
            recency_factor = max(0.1, 1.0 - (time_diff / (7 * 24 * 3600)))
            role_factor = 1.2 if message.role == "assistant" else 1.0
            length_factor = min(2.0, 1.0 + len(message.content) / 1000)
            message.relevance_score = recency_factor * role_factor * length_factor

    def prune_messages(self, max_tokens: int = 3000, min_messages: int = 6) -> None:
        if self.total_tokens <= max_tokens or len(self.messages) <= min_messages:
            return

        system_messages = [msg for msg in self.messages if msg.role == "system"]
        recent_messages = self.messages[-min_messages:]

        other_messages = [
            msg for msg in self.messages[:-min_messages] if msg not in system_messages
        ]
        other_messages.sort(key=lambda x: x.relevance_score, reverse=True)

        kept_messages = system_messages[:]
        current_tokens = sum(
            msg.token_count for msg in system_messages + recent_messages
        )

        for message in other_messages:
            if current_tokens + message.token_count <= max_tokens - sum(
                msg.token_count for msg in recent_messages
            ):
                kept_messages.append(message)
                current_tokens += message.token_count
            else:
                break

        all_kept = kept_messages + recent_messages
        all_kept.sort(key=lambda x: x.timestamp)

        self.messages = all_kept
        self.total_tokens = sum(msg.token_count for msg in self.messages)

    def get_mistral_messages(self) -> list[dict[str, str]]:
        return [msg.to_mistral_message() for msg in self.messages]

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "total_tokens": self.total_tokens,
            "conversation_summary": self.conversation_summary,
            "topic_keywords": self.topic_keywords,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationContext:
        messages = [
            ConversationMessage.from_dict(msg_data) for msg_data in data["messages"]
        ]
        return cls(
            channel_id=data["channel_id"],
            messages=messages,
            created_at=data["created_at"],
            last_activity=data["last_activity"],
            total_tokens=data["total_tokens"],
            conversation_summary=data.get("conversation_summary", ""),
            topic_keywords=data.get("topic_keywords", []),
        )


class ContextManager:
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            project_root = Path(__file__).parent.parent
            data_dir = project_root / "data" / "conversations"

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.active_contexts: dict[str, ConversationContext] = {}

        self.max_context_tokens = 4000
        self.max_conversations = 50
        self.conversation_timeout = 24 * 3600
        self.cleanup_interval = 3600

        self._cleanup_task = None
        self._cleanup_started = False

    def _start_cleanup_task(self) -> None:
        if self._cleanup_started:
            return

        async def cleanup_loop():
            while True:
                try:
                    await self._cleanup_old_conversations()
                    await asyncio.sleep(self.cleanup_interval)
                except Exception as e:
                    print(f"Error in context cleanup: {e}")
                    await asyncio.sleep(60)

        try:
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(cleanup_loop())
                self._cleanup_started = True
        except RuntimeError:
            pass

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def _get_context_file(self, channel_id: str) -> Path:
        return self.data_dir / f"context_{channel_id}.json"

    async def _save_context(self, context: ConversationContext) -> None:
        try:
            context_file = self._get_context_file(context.channel_id)
            with open(context_file, "w") as f:
                json.dump(context.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Error saving context for channel {context.channel_id}: {e}")

    async def _load_context(self, channel_id: str) -> ConversationContext | None:
        try:
            context_file = self._get_context_file(channel_id)
            if context_file.exists():
                with open(context_file) as f:
                    data = json.load(f)
                return ConversationContext.from_dict(data)
        except Exception as e:
            print(f"Error loading context for channel {channel_id}: {e}")
        return None

    async def get_conversation_context(
        self, channel_id: str, create_if_missing: bool = True
    ) -> ConversationContext | None:
        self._start_cleanup_task()

        if channel_id in self.active_contexts:
            return self.active_contexts[channel_id]

        context = await self._load_context(channel_id)
        if context:
            self.active_contexts[channel_id] = context
            return context

        if create_if_missing:
            context = ConversationContext(
                channel_id=channel_id,
                messages=[],
                created_at=time.time(),
                last_activity=time.time(),
            )
            self.active_contexts[channel_id] = context
            return context

        return None

    async def add_user_message(
        self, channel_id: str, message: discord.Message
    ) -> ConversationContext:
        context = await self.get_conversation_context(channel_id)

        conv_message = ConversationMessage(
            id=str(message.id),
            author_id=str(message.author.id),
            author_name=message.author.display_name,
            content=message.content,
            timestamp=message.created_at.timestamp(),
            role="user",
            is_bot=message.author.bot,
            token_count=self._estimate_tokens(message.content),
        )

        context.add_message(conv_message)
        context.prune_messages(self.max_context_tokens)
        await self._save_context(context)

        return context

    async def add_bot_response(
        self, channel_id: str, response_content: str, response_message_id: str = None
    ) -> ConversationContext:
        context = await self.get_conversation_context(channel_id)

        conv_message = ConversationMessage(
            id=response_message_id or f"bot_{int(time.time())}",
            author_id="bot",
            author_name="Okapi",
            content=response_content,
            timestamp=time.time(),
            role="assistant",
            is_bot=True,
            token_count=self._estimate_tokens(response_content),
        )

        context.add_message(conv_message)
        context.prune_messages(self.max_context_tokens)
        await self._save_context(context)

        return context

    async def get_recent_messages(
        self, channel_id: str, limit: int = 10
    ) -> list[ConversationMessage]:
        context = await self.get_conversation_context(
            channel_id, create_if_missing=False
        )
        if not context:
            return []

        return context.messages[-limit:] if context.messages else []

    async def clear_conversation(self, channel_id: str) -> None:
        if channel_id in self.active_contexts:
            del self.active_contexts[channel_id]

        context_file = self._get_context_file(channel_id)
        if context_file.exists():
            context_file.unlink()

    async def _cleanup_old_conversations(self) -> None:
        current_time = time.time()

        to_remove = []
        for channel_id, context in self.active_contexts.items():
            if current_time - context.last_activity > self.conversation_timeout:
                to_remove.append(channel_id)

        for channel_id in to_remove:
            await self._save_context(self.active_contexts[channel_id])
            del self.active_contexts[channel_id]

        if len(self.active_contexts) > self.max_conversations:
            sorted_contexts = sorted(
                self.active_contexts.items(), key=lambda x: x[1].last_activity
            )

            to_archive = len(self.active_contexts) - self.max_conversations
            for channel_id, context in sorted_contexts[:to_archive]:
                await self._save_context(context)
                del self.active_contexts[channel_id]

        print(
            f"Context cleanup completed. Active conversations: {len(self.active_contexts)}"
        )

    async def get_conversation_summary(self, channel_id: str) -> str:
        context = await self.get_conversation_context(
            channel_id, create_if_missing=False
        )
        if not context:
            return "No conversation found"

        message_count = len(context.messages)
        user_messages = sum(1 for msg in context.messages if not msg.is_bot)
        bot_messages = sum(1 for msg in context.messages if msg.is_bot)

        age_hours = (time.time() - context.created_at) / 3600
        inactive_hours = (time.time() - context.last_activity) / 3600

        return (
            f"Channel: {channel_id}\n"
            f"Messages: {message_count} ({user_messages} user, {bot_messages} bot)\n"
            f"Tokens: {context.total_tokens}\n"
            f"Age: {age_hours:.1f}h, Last activity: {inactive_hours:.1f}h ago"
        )

    def shutdown(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()

        import json

        for context in self.active_contexts.values():
            try:
                context_file = self._get_context_file(context.channel_id)
                with open(context_file, "w") as f:
                    json.dump(context.to_dict(), f, indent=2)
            except Exception as e:
                print(f"Error saving context for channel {context.channel_id}: {e}")
