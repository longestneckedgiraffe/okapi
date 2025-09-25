import discord
from discord.ext import commands

from config import DISCORD_TOKEN, GUILD_ID
from commands.ping import ping
from commands.ask import ask


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

TARGET_GUILD = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None

# Register commands either guild-scoped or global (not both)
if TARGET_GUILD:
    bot.tree.add_command(ping, guild=TARGET_GUILD)
    bot.tree.add_command(ask, guild=TARGET_GUILD)
else:
    bot.tree.add_command(ping)
    bot.tree.add_command(ask)


@bot.event
async def on_ready():
    print(f"{bot.user} has initialized")

    print(
        f"Commands in tree before sync: {[cmd.name for cmd in bot.tree.get_commands()]}"
    )

    try:
        if TARGET_GUILD:
            synced_guild = await bot.tree.sync(guild=TARGET_GUILD)
            print(f"Synced {len(synced_guild)} command(s) to guild {TARGET_GUILD.id}")

            synced_global = await bot.tree.sync()
            print(f"Synced {len(synced_global)} command(s) globally (cleanup)")

            for command in synced_guild:
                print(f"Synced guild command: {command.name}")
            for command in synced_global:
                print(f"Synced global command: {command.name}")
        else:
            synced_global = await bot.tree.sync()
            print(f"Synced {len(synced_global)} command(s) globally")

            for command in synced_global:
                print(f"Synced global command: {command.name}")

            for guild in bot.guilds:
                try:
                    cleaned = await bot.tree.sync(guild=guild)
                    print(f"Ensured {len(cleaned)} command(s) for guild {guild.id}")
                except Exception as guild_sync_error:
                    print(f"Failed to sync guild {guild.id}: {guild_sync_error}")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")

bot.run(DISCORD_TOKEN)
