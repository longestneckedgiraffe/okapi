import os
import time
from dotenv import load_dotenv

# Load environment variables (plan to make this ram-only in the future for security)
load_dotenv()

DISCORD_TOKEN: str | None = os.getenv("DISCORD_TOKEN")
GUILD_ID: str | None = os.getenv("GUILD_ID")

# Mistral configuration
MISTRAL_API_KEY: str | None = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL: str = os.getenv(
    "MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions"
)

MISTRAL_MODEL_ID: str = os.getenv("MISTRAL_MODEL_ID", "ministral-8b-latest")
MODEL_DISPLAY_NAME: str = os.getenv("MODEL_DISPLAY_NAME", "ministral-8b-latest")

BOT_START_TIME_EPOCH_S: float = time.time()
