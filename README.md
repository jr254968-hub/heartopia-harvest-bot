# Heartopia Harvest Discord Bot

A manual crop timer bot shared by everyone in one or more Discord servers. Each player starts a timer after planting; the bot posts a mention when it is ready.

## Requirements
- Python 3.10 or newer
- A Discord account and a Discord server where you can add bots

## Setup
1. Create an application at https://discord.com/developers/applications
2. Open **Bot** → create/reset the bot token. Keep it secret.
3. Open **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot permissions: `View Channels`, `Send Messages`, `Embed Links` (Embed Links is optional)
   - Open the generated invite URL and add the bot to your server.
4. Install Python 3.10+.
5. Extract this ZIP, open a terminal in the extracted folder, and run:
   - Windows: `py -m pip install -r requirements.txt`
   - macOS/Linux: `python3 -m pip install -r requirements.txt`
6. Copy `.env.example` to `.env` and paste your bot token after `DISCORD_TOKEN=`.
7. Start the bot:
   - Windows: `py bot.py`
   - macOS/Linux: `python3 bot.py`
8. In your Discord server, run `/setchannel` and choose the channel for alerts.

## Commands
- `/plant` — choose a crop from the dropdown; the bot automatically uses its saved growth time.
- `/mycrops` — privately list your crop timers and IDs.
- `/garden` — show the server's crop timers.
- `/harvest crop_id` — remove one of your harvested crops.
- `/cancel crop_id` — cancel one of your timers.
- `/setchannel channel` — choose the alert channel (requires Manage Server).
- `/help` — show command help.

## Duration format
**Important:** Crop timers use documented base growth times. Event crops may disappear from the game, and growth boosters or future game updates can change actual times. The bot does not connect to Heartopia itself.

## Keep it running
The bot only sends alerts while its Python program is running and connected to Discord. Keep the computer awake, or later host it on an always-on server. Timers are stored in SQLite, so they survive bot restarts; missed alerts are sent after it comes back online.

## Troubleshooting
- If slash commands do not appear, wait a few minutes, restart the bot, and confirm it was invited with both `bot` and `applications.commands` scopes.
- If alerts do not post, check that the bot can view and send messages in the selected channel.
- Never share your bot token or upload your `.env` file publicly.


## Crop timer notes
The dropdown includes regular crops and some event crops. Timings are preset base values from community crop databases and may change with game updates or growth boosts. Check the in-game timer if exact timing matters.
