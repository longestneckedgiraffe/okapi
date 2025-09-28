from __future__ import annotations

import discord
from discord import app_commands

from embeds import build_error_embed, build_success_embed
from config import MODEL_DISPLAY_NAME
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

        embed = build_success_embed(
            "Response", answer_text, footer_text=MODEL_DISPLAY_NAME
        )
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
