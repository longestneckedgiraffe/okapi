import discord
from discord.ext import commands
import signal
import sys

from config import DISCORD_TOKEN, GUILD_ID, GUILD_IDS
from commands import (
    ping,
    ask,
    amnesia_command,
    usage_command,
    security_command,
    privacy_command,
    get_context_manager,
)


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Build a de-duplicated list of allowed guilds. If provided, we only register per-guild (no globals).
# This system is overly-complex due to bot latency in updating commands (09-30-25)
allowed_guild_ids = set()
if GUILD_ID:
    try:
        allowed_guild_ids.add(int(GUILD_ID))
    except Exception:
        pass
for gid in GUILD_IDS or []:
    try:
        allowed_guild_ids.add(int(gid))
    except Exception:
        pass

ALLOWED_GUILDS = [discord.Object(id=g) for g in sorted(allowed_guild_ids)]


@bot.event
async def on_ready():
    print(f"{bot.user} has initialized")

    print(
        f"Commands in tree before sync: {[cmd.name for cmd in bot.tree.get_commands()]}"
    )

    try:
        bot.tree.clear_commands(guild=None)

        if ALLOWED_GUILDS:
            for g in ALLOWED_GUILDS:
                bot.tree.clear_commands(guild=g)
                bot.tree.add_command(ping, guild=g)
                bot.tree.add_command(ask, guild=g)
                bot.tree.add_command(amnesia_command, guild=g)
                bot.tree.add_command(usage_command, guild=g)
                bot.tree.add_command(security_command, guild=g)
                bot.tree.add_command(privacy_command, guild=g)
                synced = await bot.tree.sync(guild=g)
                print(f"Synced {len(synced)} command(s) to guild {g.id}")
            cleaned = await bot.tree.sync()
            print(f"Cleared global commands; now {len(cleaned)} present globally")
        else:
            bot.tree.add_command(ping)
            bot.tree.add_command(ask)
            bot.tree.add_command(amnesia_command)
            bot.tree.add_command(usage_command)
            bot.tree.add_command(security_command)
            bot.tree.add_command(privacy_command)
            synced_global = await bot.tree.sync()
            print(f"Synced {len(synced_global)} command(s) globally")

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
    print(f"\nReceived signal {signum} (Shutting down)")
    context_mgr, _ = get_context_manager()
    context_mgr.shutdown()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Semi-graceful shutdown handling
try:
    bot.run(DISCORD_TOKEN)
except KeyboardInterrupt:
    print("\nShutting down")
    context_mgr, _ = get_context_manager()
    context_mgr.shutdown()
except Exception as e:
    print(f"Crash: {e}")
    context_mgr, _ = get_context_manager()
    context_mgr.shutdown()
    raise
