from __future__ import annotations

import discord
from discord import app_commands

from datetime import datetime, timezone

from embeds import build_error_embed, build_success_embed
from config import MODEL_DISPLAY_NAME
from mistral_client import MistralClient
from context_tools import process_tool_calls
from commands.shared import get_context_manager


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
                    "Address them by name only during greeting and do not invent personal details."
                ),
            },
            {
                "role": "system",
                "content": (
                    "You have access to conversation history tools. You should use them for virtually all messages to maintain conversational continuity:\n"
                    "- Use 'fetch_recent_messages' by default to understand the conversation flow and provide contextually relevant responses.\n"
                    "- Use 'search_conversation_history' when the user asks about specific past topics or when recent messages aren't sufficient.\n"
                    "- ONLY skip context tools if the user is asking a completely standalone question that has no possible relation to previous conversation (e.g., 'what is 2+2?', 'define photosynthesis').\n"
                    "When in doubt, fetch context. Better to have context and not need it than to miss important conversational cues."
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

        # Some providers return content as a list of parts; normalize to string, this is not an issue for Mistral
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
