import os
import time
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN: str | None = os.getenv("DISCORD_TOKEN")

# Handle both singular GUILD_ID and GUILD_IDS in .env
GUILD_ID: str | None = os.getenv("GUILD_ID")
_GUILD_IDS_RAW = os.getenv("GUILD_IDS", "").strip()
GUILD_IDS: list[int] = (
    [int(x.strip()) for x in _GUILD_IDS_RAW.split(",") if x.strip()]
    if _GUILD_IDS_RAW
    else []
)

MISTRAL_API_KEY: str | None = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL: str = os.getenv(
    "MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions"
)

MISTRAL_MODEL_ID: str = os.getenv("MISTRAL_MODEL_ID", "magistral-small-latest")
MODEL_DISPLAY_NAME: str = os.getenv("MODEL_DISPLAY_NAME", "magistral-small-latest")
MODEL_TEMPERATURE: float = float(os.getenv("MODEL_TEMPERATURE", "0.7"))

BOT_START_TIME_EPOCH_S: float = time.time()
DATA_ENCRYPTION_KEY: str | None = os.getenv("DATA_ENCRYPTION_KEY")
