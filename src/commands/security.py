from __future__ import annotations

import discord
from discord import app_commands

from config import DATA_ENCRYPTION_KEY


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
