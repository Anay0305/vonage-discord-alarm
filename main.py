#!/usr/bin/env python3
"""
Discord Alarm Bot — calls you via Vonage before your alarm goes off.

Usage:
    python main.py
    python main.py --phone 919876543210   # override phone number

Setup:
    1. Copy .env.example to .env and fill in your credentials
    2. Make sure WEBHOOK_BASE_URL is publicly accessible (use ngrok for local dev)
    3. Drop an alarm.mp3 in this folder (optional, falls back to TTS)

Discord commands:
    /alarm set 08:30      — Set alarm for 08:30, calls you at 08:25
    /alarm list           — Show active alarms
    /alarm cancel 1       — Cancel alarm_1
    /alarm test           — Trigger an immediate test call
"""

import argparse
import asyncio
import sys
import uvicorn

import config
from discord_bot import bot, tree, alarm_group
from webhook_server import app
from alarms import alarm_manager


def parse_args():
    parser = argparse.ArgumentParser(description="Discord Alarm Bot")
    parser.add_argument(
        "--phone",
        help=f"Phone number to call (default: {config.PHONE_NUMBER})",
        default=None,
    )
    return parser.parse_args()


def validate_config():
    errors = []

    if not config.DISCORD_BOT_TOKEN:
        errors.append("DISCORD_BOT_TOKEN is not set")

    if not config.VONAGE_APPLICATION_ID:
        errors.append("VONAGE_APPLICATION_ID is not set")

    if not config.VONAGE_FROM_NUMBER:
        errors.append("VONAGE_FROM_NUMBER is not set")

    if not config.WEBHOOK_BASE_URL:
        errors.append("WEBHOOK_BASE_URL is not set")

    if errors:
        print("❌  Missing required .env values:")
        for e in errors:
            print(f"    • {e}")
        print("\n    Copy .env.example to .env and fill in the values.")
        sys.exit(1)


async def main():
    args = parse_args()

    # Override phone number if passed via CLI
    if args.phone:
        config.PHONE_NUMBER = args.phone

    validate_config()

    print("=" * 55)
    print("    Discord Alarm Bot")
    print("=" * 55)
    print(f"  Webhook URL:  {config.WEBHOOK_BASE_URL}")
    print(f"  Webhook Port: {config.WEBHOOK_PORT}")
    print(f"  Calling:      +{config.PHONE_NUMBER}")
    print(f"  Timezone:     {config.TIMEZONE}")
    print("=" * 55)
    print()

    if "your-domain.com" in config.WEBHOOK_BASE_URL or "ngrok.io" not in config.WEBHOOK_BASE_URL and "http" in config.WEBHOOK_BASE_URL:
        pass  # URL looks fine, skip warning

    uvicorn_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=config.WEBHOOK_PORT,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(uvicorn_config)

    tree.add_command(alarm_group)

    print("🚀 Starting bot and webhook server...\n")

    try:
        await asyncio.gather(
            bot.start(config.DISCORD_BOT_TOKEN),
            server.serve(),
        )
    except KeyboardInterrupt:
        pass
    finally:
        await alarm_manager.stop_scheduler()
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
