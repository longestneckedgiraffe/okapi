# Okapi

Okapi is a basic Discord chatbot, using [Mistral](https://docs.mistral.ai/getting-started/models/models_overview/)

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install Okapi's requirements in order to run it locally

```bash
# Note: It's highly recommended to use a venv
pip install -r requirements.txt
```

## Setup

1. Copy `.env.example` to `.env` and add your fields
   - `DISCORD_TOKEN`
   - `GUILD_IDS`
   - `MISTRAL_API_KEY`

2. Run the bot
```bash
python src/bot.py
```

3. Use `/ask` in Discord to chat with Okapi

## Contributing

There's currently no plans for contribution

## License

[MIT](https://opensource.org/license/mit)
