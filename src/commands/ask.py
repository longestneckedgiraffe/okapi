from __future__ import annotations

import discord
from discord import app_commands

from embeds import build_error_embed, build_success_embed
from mistral_client import MistralClient


@app_commands.command(name="ask", description="Ask Okapi a question")
@app_commands.describe(query="Your question for Okapi")
async def ask(interaction: discord.Interaction, query: str):
    client = MistralClient()

    try:
        # Sets the bot to "think" while response is being fetched
        await interaction.response.defer(thinking=True)

        data = await client.create_chat_completion(query)
        # Safe data extraction
        try:
            answer_text = (
                (data.get("choices") or [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
        except Exception:
            answer_text = ""
        if not answer_text:
            answer_text = "(No content returned by the model)"

        embed = build_success_embed("Response", answer_text)
        embed.add_field(name="Question", value=query[:1024], inline=False)
        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(
            embed=build_error_embed("Mistral error", str(e)),
            ephemeral=True,
        )
