from __future__ import annotations

import discord
from datetime import datetime, timezone


SUCCESS_COLOR = discord.Color(0x7ED957)
ERROR_COLOR = discord.Color(0xE74C3C)


def build_success_embed(
    title: str, description: str, footer_text: str | None = "No model"
) -> discord.Embed:
    embed = discord.Embed(
        title=title, description=description[:4096], color=SUCCESS_COLOR
    )
    embed.set_footer(text=footer_text or "No model")
    embed.timestamp = datetime.now(timezone.utc)
    return embed


def build_error_embed(
    title: str, description: str, footer_text: str | None = "No model"
) -> discord.Embed:
    embed = discord.Embed(
        title=title, description=description[:1000], color=ERROR_COLOR
    )
    embed.set_footer(text=footer_text or "No model")
    embed.timestamp = datetime.now(timezone.utc)
    return embed
