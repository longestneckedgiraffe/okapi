from __future__ import annotations


import discord
from discord import app_commands

from embeds import build_error_embed, build_success_embed
from commands.shared import get_context_manager


@app_commands.command(
    name="amnesia",
    description="Clear conversation history for this channel",
)
@app_commands.describe(
    count="Number of recent messages to delete (leave empty to clear all)",
)
async def amnesia_command(
    interaction: discord.Interaction,
    count: int | None = None,
):
    channel_id = str(interaction.channel_id)
    context_mgr, _ = get_context_manager()

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

    total_messages = len(context.messages)

    if count is not None and count <= 0:
        embed = build_error_embed(
            "Invalid Count",
            "Please specify a positive number of messages to delete.",
            footer_text="No model",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if count is None or count >= total_messages:
        # Clear all messages
        await context_mgr.clear_conversation(channel_id)
        embed = build_success_embed(
            "Memory Cleared",
            f"Successfully cleared all {total_messages} messages from conversation history.",
            footer_text="No model",
        )
    else:
        # Clear last N messages
        context.messages = context.messages[:-count]
        context.total_tokens = sum(msg.token_count for msg in context.messages)
        await context_mgr._save_context(context)

        embed = build_success_embed(
            "Memory Cleared",
            f"Successfully deleted {count} recent messages. {len(context.messages)} messages remaining.",
            footer_text="No model",
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)
