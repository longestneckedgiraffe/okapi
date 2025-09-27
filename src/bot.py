import discord
from discord.ext import commands
import signal
import sys

from config import DISCORD_TOKEN, GUILD_ID
from commands.ping import ping
from commands.ask import ask, amnesia_command, usage_command, get_context_manager


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

TARGET_GUILD = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None

if TARGET_GUILD:
    bot.tree.add_command(ping, guild=TARGET_GUILD)
    bot.tree.add_command(ask, guild=TARGET_GUILD)
    bot.tree.add_command(amnesia_command, guild=TARGET_GUILD)
    bot.tree.add_command(usage_command, guild=TARGET_GUILD)
else:
    bot.tree.add_command(ping)
    bot.tree.add_command(ask)
    bot.tree.add_command(amnesia_command)
    bot.tree.add_command(usage_command)


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


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    channel_id = str(message.channel.id)

    context_mgr, _ = get_context_manager()

    existing_context = await context_mgr.get_conversation_context(
        channel_id, create_if_missing=False
    )

    if existing_context and not message.content.startswith("/"):
        try:
            await context_mgr.add_user_message(channel_id, message)
        except Exception as e:
            print(f"Error storing message context: {e}")

    await bot.process_commands(message)


if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")


def signal_handler(signum, frame):
    print(f"\nReceived signal {signum}. Shutting down gracefully...")
    context_mgr, _ = get_context_manager()
    context_mgr.shutdown()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

try:
    bot.run(DISCORD_TOKEN)
except KeyboardInterrupt:
    print("\nShutting down...")
    context_mgr, _ = get_context_manager()
    context_mgr.shutdown()
except Exception as e:
    print(f"Bot crashed: {e}")
    context_mgr, _ = get_context_manager()
    context_mgr.shutdown()
    raise
