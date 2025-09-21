import discord
from discord.ext import commands
from discord import app_commands
import os
import platform
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

GUILD_ID = os.getenv('GUILD_ID')
TARGET_GUILD = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None

BOT_START_TIME_EPOCH_S = time.time()

@app_commands.command(name='ping', description="Returns the bot's latency")
@app_commands.describe(verbose="Include diagnostic info (ephemeral)")
async def ping(interaction: discord.Interaction, verbose: bool = False):
    latency_ms = round(bot.latency * 1000)

    responded_at = datetime.now(timezone.utc)
    embed = discord.Embed(
        title="Pong!",
        description="Bark!",
        color=discord.Color(0x7ed957),
    )
    embed.add_field(name="Latency", value=f"{latency_ms} ms", inline=True)

    if verbose:
        uptime_seconds = max(0, int(time.time() - BOT_START_TIME_EPOCH_S))
        uptime_str = str(timedelta(seconds=uptime_seconds))

        bot_identity = (
            f"{bot.user} ({getattr(bot.user, 'id', 'unknown')})" if bot.user else "unknown"
        )
        scope_str = f"guild {interaction.guild.id}" if interaction.guild else "direct_message"

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

    embed.set_footer(
        text="No model"
    )
    embed.timestamp = responded_at

    await interaction.response.send_message(
        embed=embed, ephemeral=(verbose and interaction.guild is not None)
    )

# Register the command either guild-scoped or global (not both)
if TARGET_GUILD:
    bot.tree.add_command(ping, guild=TARGET_GUILD)
else:
    bot.tree.add_command(ping)

@bot.event
async def on_ready():
    print(f'{bot.user} has initialized')
    
    print(f'Commands in tree before sync: {[cmd.name for cmd in bot.tree.get_commands()]}')

    try:
        if TARGET_GUILD:
            synced_guild = await bot.tree.sync(guild=TARGET_GUILD)
            print(f'Synced {len(synced_guild)} command(s) to guild {TARGET_GUILD.id}')

            synced_global = await bot.tree.sync()
            print(f'Synced {len(synced_global)} command(s) globally (cleanup)')

            for command in synced_guild:
                print(f'Synced guild command: {command.name}')
            for command in synced_global:
                print(f'Synced global command: {command.name}')
        else:
            synced_global = await bot.tree.sync()
            print(f'Synced {len(synced_global)} command(s) globally')

            for command in synced_global:
                print(f'Synced global command: {command.name}')

            for guild in bot.guilds:
                try:
                    cleaned = await bot.tree.sync(guild=guild)
                    print(f'Ensured {len(cleaned)} command(s) for guild {guild.id}')
                except Exception as guild_sync_error:
                    print(f'Failed to sync guild {guild.id}: {guild_sync_error}')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

bot.run(os.getenv('DISCORD_TOKEN'))