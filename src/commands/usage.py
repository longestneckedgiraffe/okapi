from __future__ import annotations

import time as _time

import discord
from discord import app_commands

from commands.shared import get_context_manager


@app_commands.command(
    name="usage", description="Show conversation context and usage statistics"
)
@app_commands.describe(
    detailed="Show detailed conversation information including recent messages"
)
async def usage_command(interaction: discord.Interaction, detailed: bool = False):
    channel_id = str(interaction.channel_id)
    context_mgr, _ = get_context_manager()

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
