from __future__ import annotations

import platform
import time
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands

from config import BOT_START_TIME_EPOCH_S, MODEL_DISPLAY_NAME


@app_commands.command(name="ping", description="Returns the bot's latency")
@app_commands.describe(verbose="Include diagnostic info (ephemeral)")
async def ping(interaction: discord.Interaction, verbose: bool = False):
    bot = interaction.client
    latency_ms = round(bot.latency * 1000)

    responded_at = datetime.now(timezone.utc)
    embed = discord.Embed(
        title="Pong!",
        description="Bark!",
        color=discord.Color(0x7ED957),
    )
    embed.add_field(name="Latency", value=f"{latency_ms} ms", inline=True)

    if verbose:
        uptime_seconds = max(0, int(time.time() - BOT_START_TIME_EPOCH_S))
        uptime_str = str(timedelta(seconds=uptime_seconds))

        bot_identity = (
            f"{bot.user} ({getattr(bot.user, 'id', 'unknown')})"
            if bot.user
            else "unknown"
        )
        scope_str = (
            f"guild {interaction.guild.id}" if interaction.guild else "direct_message"
        )

        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="Scope", value=scope_str, inline=True)
        embed.add_field(name="discord.py", value=discord.__version__, inline=True)
        embed.add_field(name="Python", value=platform.python_version(), inline=True)
        embed.add_field(name="Shard(s)", value=str(bot.shard_count or 1), inline=True)
        embed.add_field(
            name="Commands",
            value=str(len(bot.tree.get_commands())),
            inline=True,
        )
        embed.add_field(
            name="Intents.message_content",
            value=str(bot.intents.message_content),
            inline=True,
        )
        embed.add_field(name="Bot", value=bot_identity, inline=False)

    embed.set_footer(text=MODEL_DISPLAY_NAME)
    embed.timestamp = responded_at

    await interaction.response.send_message(
        embed=embed, ephemeral=(verbose and interaction.guild is not None)
    )
