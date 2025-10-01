from __future__ import annotations

import discord
from discord import app_commands

from datetime import datetime, timezone

from embeds import build_error_embed, build_success_embed
from config import MODEL_DISPLAY_NAME, DATA_ENCRYPTION_KEY
from mistral_client import MistralClient
from context_manager import ContextManager
from context_tools import ContextTools, process_tool_calls


context_manager = None
context_tools = None


def get_context_manager():
    global context_manager, context_tools
    if context_manager is None:
        context_manager = ContextManager()
        context_tools = ContextTools(context_manager)
    return context_manager, context_tools


@app_commands.command(name="ask", description="Ask Okapi a question (context-aware)")
@app_commands.describe(query="Your question for Okapi")
async def ask(interaction: discord.Interaction, query: str):
    client = MistralClient()
    channel_id = str(interaction.channel_id)
    context_mgr, ctx_tools = get_context_manager()

    try:
        await interaction.response.defer(thinking=True)

        mock_message = type(
            "MockMessage",
            (),
            {
                "id": interaction.id,
                "author": interaction.user,
                "content": query,
                "created_at": discord.utils.utcnow(),
            },
        )()

        # Store the message but DON'T automatically load conversation history
        await context_mgr.add_user_message(channel_id, mock_message)

        tools = ctx_tools.get_tool_definitions()

        user_preferred_name = (
            getattr(interaction.user, "global_name", None)
            or getattr(interaction.user, "display_name", None)
            or getattr(interaction.user, "name", None)
            or "the user"
        )

        current_datetime = datetime.now(timezone.utc).strftime(
            "%A, %B %d, %Y at %I:%M %p UTC"
        )

        conversation_messages = [
            {
                "role": "system",
                "content": f"The current date and time is {current_datetime}.",
            },
            {
                "role": "system",
                "content": (
                    f"The current user's preferred name is '{user_preferred_name}'. "
                    "Address them by name when appropriate and do not invent personal details."
                ),
            },
            {
                "role": "system",
                "content": (
                    "You have access to conversation history tools. Use them ONLY when necessary:\n"
                    "- Use 'fetch_recent_messages' if the user references previous messages, asks follow-up questions, or mentions 'earlier', 'before', 'previously', etc.\n"
                    "- Use 'search_conversation_history' if the user asks about specific past topics or conversations.\n"
                    "- For simple, standalone questions that don't require prior context, respond directly without using tools.\n"
                    "Be efficient - don't fetch context unless it's needed to answer the question properly."
                ),
            },
            {
                "role": "system",
                "content": (
                    "Tone and formality guidelines:\n"
                    "1. SENSITIVE TOPICS (terrorism, violence, death, tragedy, war crimes, genocide, serious historical atrocities):\n"
                    "   - ALWAYS use formal, respectful tone regardless of user's style\n"
                    "   - NEVER use emojis, casual phrases, or exclamation marks\n"
                    "   - Be factual, clear, and appropriately serious\n"
                    "2. CASUAL TOPICS (general chat, lighthearted questions, everyday topics):\n"
                    "   - Match the user's tone and energy\n"
                    "   - If they write in lowercase, you can too\n"
                    "   - Be playful with playful messages\n"
                    "\n"
                    "3. TECHNICAL/EDUCATIONAL TOPICS:\n"
                    "   - Use clear, professional language\n"
                    "   - Be concise and informative\n"
                    "\n"
                    "Read the context and adapt appropriately. When in doubt about sensitivity, err on the side of formality."
                ),
            },
            {
                "role": "user",
                "content": query,
            },
        ]

        data = await client.create_context_aware_completion(
            conversation_messages=conversation_messages, tools=tools
        )

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        # Track if context was actually used
        context_tools_used = False
        tools_called = []

        if message.get("tool_calls"):
            tool_results = await process_tool_calls(
                message["tool_calls"],
                ctx_tools,
                channel_id,
                interaction.channel if hasattr(interaction, "channel") else None,
            )

            # Track which tools were called
            for tool_call in message["tool_calls"]:
                tool_name = tool_call.get("function", {}).get("name", "")
                tools_called.append(tool_name)
                if tool_name in [
                    "fetch_recent_messages",
                    "search_conversation_history",
                ]:
                    context_tools_used = True

            conversation_messages.append(
                {
                    "role": "assistant",
                    "content": message.get("content", ""),
                    "tool_calls": message["tool_calls"],
                }
            )

            for tool_result in tool_results:
                conversation_messages.append(tool_result)

            data = await client.create_chat_completion(messages=conversation_messages)

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})

        # Some providers return content as a list of parts; normalize to string
        raw_content = message.get("content", "")
        if isinstance(raw_content, list):
            parts: list[str] = []
            for part in raw_content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict):
                    text_val = (
                        part.get("text") or part.get("content") or part.get("value")
                    )
                    if isinstance(text_val, str):
                        parts.append(text_val)
            answer_text = "\n".join([p for p in parts if p]).strip()
        elif isinstance(raw_content, str):
            answer_text = raw_content.strip()
        else:
            answer_text = str(raw_content)
        if not answer_text:
            answer_text = "(No content returned by the model)"

        await context_mgr.add_bot_response(channel_id, answer_text)

        embed = build_success_embed(
            "Response", answer_text, footer_text=MODEL_DISPLAY_NAME
        )
        embed.add_field(name="Question", value=query[:1024], inline=False)

        # Only show context usage if tools were actually called
        if context_tools_used:
            embed.add_field(
                name="Context",
                value="Used conversation history",
                inline=True,
            )
        elif tools_called:
            embed.add_field(
                name="Tools Used",
                value=", ".join(tools_called),
                inline=True,
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(
            embed=build_error_embed("Mistral error", str(e), footer_text="No model"),
            ephemeral=True,
        )


@app_commands.command(
    name="amnesia", description="Clear conversation history for this channel"
)
async def amnesia_command(interaction: discord.Interaction):
    channel_id = str(interaction.channel_id)
    context_mgr, ctx_tools = get_context_manager()

    context = await context_mgr.get_conversation_context(
        channel_id, create_if_missing=False
    )

    if not context or not context.messages:
        embed = build_success_embed(
            "No Memory Found",
            "There's no conversation history to clear in this channel.",
            footer_text="No model",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await context_mgr.clear_conversation(channel_id)
    embed = build_success_embed(
        "Memory Cleared",
        f"Successfully cleared {len(context.messages)} messages from conversation history.",
        footer_text="No model",
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@app_commands.command(
    name="usage", description="Show conversation context and usage statistics"
)
@app_commands.describe(
    detailed="Show detailed conversation information including recent messages"
)
async def usage_command(interaction: discord.Interaction, detailed: bool = False):
    channel_id = str(interaction.channel_id)
    context_mgr, ctx_tools = get_context_manager()

    context = await context_mgr.get_conversation_context(
        channel_id, create_if_missing=False
    )

    if not context or not context.messages:
        # Use discord.Embed with fields for all data
        embed = discord.Embed(
            title="No Conversation Data", color=discord.Color(0x7ED957)
        )
        embed.add_field(
            name="Status",
            value="No conversation history found for this channel.",
            inline=False,
        )
        embed.set_footer(text="No model")
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Build embed using discord.py's Embed and fields
    embed = discord.Embed(title="Conversation Usage", color=discord.Color(0x7ED957))
    embed.set_footer(text="No model")
    embed.timestamp = discord.utils.utcnow()

    # Individual fields
    total_messages = len(context.messages)
    user_messages = sum(1 for msg in context.messages if not msg.is_bot)
    bot_messages = total_messages - user_messages

    embed.add_field(name="Channel", value=str(channel_id), inline=True)
    embed.add_field(name="Messages", value=str(total_messages), inline=True)
    embed.add_field(name="User Messages", value=str(user_messages), inline=True)
    embed.add_field(name="Bot Messages", value=str(bot_messages), inline=True)
    embed.add_field(name="Total Tokens", value=str(context.total_tokens), inline=True)
    embed.add_field(
        name="Context Limit", value=str(context_mgr.max_context_tokens), inline=True
    )

    # Age and activity
    import time as _time

    age_hours = (_time.time() - context.created_at) / 3600
    inactive_hours = (_time.time() - context.last_activity) / 3600
    embed.add_field(name="Age", value=f"{age_hours:.1f}h", inline=True)
    embed.add_field(
        name="Last Activity", value=f"{inactive_hours:.1f}h ago", inline=True
    )

    if detailed and context.messages:
        recent_msgs = (
            context.messages[-5:] if len(context.messages) > 5 else context.messages
        )
        if recent_msgs:
            recent_text = "\n".join(
                [
                    f"**{msg.author_name}**: {msg.content[:80]}{'...' if len(msg.content) > 80 else ''}"
                    for msg in recent_msgs
                ]
            )
            embed.add_field(
                name="Recent Messages", value=recent_text[:1024], inline=False
            )

        user_tokens = sum(msg.token_count for msg in context.messages if not msg.is_bot)
        bot_tokens = sum(msg.token_count for msg in context.messages if msg.is_bot)
        embed.add_field(name="User Tokens", value=str(user_tokens), inline=True)
        embed.add_field(name="Bot Tokens", value=str(bot_tokens), inline=True)

        if context.total_tokens > context_mgr.max_context_tokens * 0.8:
            health = "Near limit"
        elif context.total_tokens > context_mgr.max_context_tokens * 0.6:
            health = "Sub-optimal"
        else:
            health = "Optimal"
        embed.add_field(name="Memory Health", value=health, inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@app_commands.command(
    name="security", description="Show encryption status and context storage details"
)
async def security_command(interaction: discord.Interaction):
    embed = discord.Embed(title="Security", color=discord.Color(0x7ED957))
    embed.set_footer(text="No model")
    embed.timestamp = discord.utils.utcnow()
    key_active = bool(DATA_ENCRYPTION_KEY and DATA_ENCRYPTION_KEY.strip())
    embed.add_field(
        name="Key Active", value=("Yes" if key_active else "No"), inline=True
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@app_commands.command(
    name="privacy", description="Okapi privacy & data handling policy"
)
async def privacy_command(interaction: discord.Interaction):
    embed = discord.Embed(title="Privacy", color=discord.Color(0x7ED957))
    embed.set_footer(text="No model")
    embed.timestamp = discord.utils.utcnow()
    embed.add_field(
        name="Encryption at Rest",
        value=(
            "Conversation data is encrypted at rest using AEAD (AES-GCM) when a server key is configured."
        ),
        inline=False,
    )
    embed.add_field(
        name="Limited Retention",
        value=(
            "Conversations are pruned for relevance and can be cleared any time with /amnesia."
        ),
        inline=False,
    )
    embed.add_field(
        name="No Sensitive Data",
        value=(
            "Okapi does not store or transmit sensitive information beyond what is needed to fulfill your request."
        ),
        inline=False,
    )
    embed.add_field(
        name="Open Source",
        value=(
            "View the code on GitHub: https://github.com/longestneckedgiraffe/okapi"
        ),
        inline=False,
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)
