import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Vonage credentials ---
VONAGE_APPLICATION_ID = os.getenv("VONAGE_APPLICATION_ID")
VONAGE_PRIVATE_KEY_PATH = os.getenv("VONAGE_PRIVATE_KEY_PATH", "private.key")
VONAGE_FROM_NUMBER = os.getenv("VONAGE_FROM_NUMBER")

# --- Phone number to call (can be overridden via CLI) ---
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "919056690327")

# --- Discord ---
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
# Set to your Discord server ID for instant slash command registration (recommended for dev).
# Leave empty to sync globally (can take up to 1 hour).
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
if DISCORD_GUILD_ID:
    DISCORD_GUILD_ID = int(DISCORD_GUILD_ID)

# --- Webhook server ---
# Vonage needs to reach this URL. Use ngrok or a public server.
# Example with ngrok: WEBHOOK_BASE_URL = "https://abcd1234.ngrok.io"
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))

# --- Alarm audio ---
# Drop an alarm.mp3 in this folder and it will be played on the call.
# If the file doesn't exist, falls back to TTS.
ALARM_AUDIO_FILE = "alarm.mp3"

# TTS fallback (used when alarm.mp3 is not found)
ALARM_TTS_TEXT = "Wake up! Wake up! This is your alarm. Say I am awake, or press any key to dismiss."
FOLLOWUP_TTS_TEXT = "Hey. Just checking. Are you still awake? Say yes or press any key."
ALARM_LANGUAGE = "en-US"

# --- Wake detection ---
# Any of these words in the transcript = alarm dismissed
WAKE_KEYWORDS = [
    "awake", "wake", "shut", "stop", "yes", "okay", "ok", "done",
    "fine", "alive", "here", "up", "ready",
]

# --- Timing ---
PREALARM_MINUTES = 5           # Start calling this many minutes before alarm time
RETRY_INTERVAL_SECONDS = 60    # Retry call this long after unanswered/no-response
MAX_RETRIES = 20               # Give up after this many failed attempts
CALL_RINGING_TIMEOUT = 60      # Seconds to wait for answer before Vonage hangs up (max 120)
CALL_MAX_DURATION = 180        # Max answered call length in seconds

# --- Follow-up calls after dismissal ---
FOLLOW_UP_COUNT = 3
FOLLOW_UP_MIN_SECONDS = 300    # 5 min minimum gap
FOLLOW_UP_MAX_SECONDS = 900    # 15 min maximum gap

# --- Timezone ---
TIMEZONE = "Asia/Kolkata"
