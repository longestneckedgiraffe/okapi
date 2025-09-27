from __future__ import annotations

import discord
from discord import app_commands

from embeds import build_error_embed, build_success_embed
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

        context = await context_mgr.add_user_message(channel_id, mock_message)

        conversation_messages = context.get_mistral_messages()

        tools = ctx_tools.get_tool_definitions()

        data = await client.create_context_aware_completion(
            conversation_messages=conversation_messages, tools=tools
        )

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        if message.get("tool_calls"):
            tool_results = await process_tool_calls(
                message["tool_calls"],
                ctx_tools,
                channel_id,
                interaction.channel if hasattr(interaction, "channel") else None,
            )

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

        answer_text = message.get("content", "").strip()
        if not answer_text:
            answer_text = "(No content returned by the model)"

        await context_mgr.add_bot_response(channel_id, answer_text)

        embed = build_success_embed("Response", answer_text)
        embed.add_field(name="Question", value=query[:1024], inline=False)

        if len(context.messages) > 2:
            embed.add_field(
                name="Context",
                value=f"Using {len(context.messages)-1} previous messages",
                inline=True,
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(
            embed=build_error_embed("Mistral error", str(e)),
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
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await context_mgr.clear_conversation(channel_id)
    embed = build_success_embed(
        "Memory Cleared",
        f"Successfully cleared {len(context.messages)} messages from conversation history.",
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
        embed = build_success_embed(
            "No Conversation Data", "No conversation history found for this channel."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    summary = await context_mgr.get_conversation_summary(channel_id)
    embed = build_success_embed("Conversation Usage", summary)

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
        embed.add_field(
            name="Token Distribution",
            value=f"User: {user_tokens} | Bot: {bot_tokens}",
            inline=True,
        )

        if context.total_tokens > context_mgr.max_context_tokens * 0.8:
            health = "⚠️ Near Limit"
        elif context.total_tokens > context_mgr.max_context_tokens * 0.6:
            health = "🟡 Moderate"
        else:
            health = "🟢 Healthy"
        embed.add_field(name="Memory Health", value=health, inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)
