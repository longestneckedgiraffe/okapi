from __future__ import annotations

import discord
from discord import app_commands


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
