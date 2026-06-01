# Discord Alarm Bot 🔔

A Discord bot that calls you via Vonage 5 minutes before your alarm time and keeps calling until you confirm you're awake.

## Features

- Set alarms via Discord slash commands
- Calls you 5 minutes before alarm time
- Plays custom MP3 or text-to-speech
- Keeps retrying until you say "I'm awake" or press any key
- Makes 2-3 random follow-up calls to ensure you didn't fall back asleep

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Discord Bot

1. Go to https://discord.com/developers/applications
2. Create a new application
3. Go to "Bot" → Reset Token → Copy the token
4. Enable "Message Content Intent" under Privileged Gateway Intents
5. Go to OAuth2 → URL Generator:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`
6. Copy the generated URL and invite the bot to your server

### 3. Configure Webhook URL

You need a publicly accessible URL for Vonage to send callbacks.

**Option A: ngrok (for testing)**
```bash
ngrok http 8080
```
Copy the HTTPS URL (e.g., `https://abcd1234.ngrok.io`)

**Option B: Deploy to a server**
Use any server with a public IP or domain.

### 4. Edit config.py

```python
DISCORD_BOT_TOKEN = "your_bot_token_here"
WEBHOOK_BASE_URL = "https://your-ngrok-url.ngrok.io"  # No trailing slash
```

Optionally set `DISCORD_GUILD_ID` to your server ID for instant command registration during development.

### 5. Add alarm sound (optional)

Drop an `alarm.mp3` file in this folder. If not present, it falls back to text-to-speech.

### 6. Run

```bash
python main.py
```

## Usage

In Discord:

- `/alarm set 08:30` — Set alarm for 8:30 AM (calls at 8:25)
- `/alarm list` — Show active alarms
- `/alarm cancel 1` — Cancel alarm_1
- `/alarm test` — Trigger an immediate test call

## How it works

1. You set an alarm for 8:30 AM
2. At 8:25 AM, the bot calls you via Vonage
3. Your phone rings and plays the alarm sound
4. You say "I'm awake" or "shut up" or press any key
5. The alarm is dismissed
6. 5-15 minutes later, it calls again to check you're still awake
7. This happens 2-3 more times randomly

## Wake phrases

Any of these words will dismiss the alarm:
- awake, wake, shut, stop, yes, okay, ok, done, fine, alive, here, up, ready

Or just press any key on your phone's keypad.

## Troubleshooting

**Commands not showing up in Discord:**
- If you set `DISCORD_GUILD_ID`, commands appear instantly
- Without it, global sync takes up to 1 hour

**Calls not working:**
- Check that `WEBHOOK_BASE_URL` is publicly accessible
- Test with: `curl https://your-url.ngrok.io/health`
- Check Vonage dashboard for call logs

**Speech recognition not working:**
- Make sure you speak clearly
- Fallback: press any key on your phone's keypad
- Check webhook logs for transcripts

## Configuration

Edit [config.py](config.py) to customize:

- `PREALARM_MINUTES` — How early to start calling (default: 5)
- `RETRY_INTERVAL_SECONDS` — Time between retries (default: 100)
- `FOLLOW_UP_COUNT` — Number of follow-up calls (default: 3)
- `WAKE_KEYWORDS` — Words that dismiss the alarm
- `ALARM_TTS_TEXT` — What the bot says if no MP3 is found

## Files

- `main.py` — Entry point
- `config.py` — Configuration
- `alarms.py` — Alarm state management + Vonage integration
- `discord_bot.py` — Discord slash commands
- `webhook_server.py` — FastAPI server for Vonage callbacks
- `test.py` — Original Vonage test script (can be deleted)

## License

MIT
