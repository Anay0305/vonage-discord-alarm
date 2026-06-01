from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import discord
from discord import app_commands

import config
from alarms import alarm_manager, AlarmStatus

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

alarm_group = app_commands.Group(name="alarm", description="Manage your alarms")


@bot.event
async def on_ready():
    alarm_manager.set_discord_bot(bot)
    await alarm_manager.start_scheduler()

    if config.DISCORD_GUILD_ID:
        guild = discord.Object(id=config.DISCORD_GUILD_ID)
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
        print(f"✅ Slash commands synced to guild {config.DISCORD_GUILD_ID}")
    else:
        await tree.sync()
        print("✅ Slash commands synced globally (may take up to 1 hour)")

    print(f"✅ Bot ready: {bot.user}")


@alarm_group.command(name="set", description="Set an alarm (will call you 5 mins early)")
@app_commands.describe(
    time="Time in HH:MM format (24h, e.g. 08:30)",
    phone="Phone number to call (optional, overrides default)",
)
async def alarm_set(interaction: discord.Interaction, time: str, phone: str = None):
    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)

    try:
        hour, minute = map(int, time.strip().split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, AttributeError):
        await interaction.response.send_message(
            "❌ Invalid time. Use 24h format like `08:30` or `22:45`.",
            ephemeral=True,
        )
        return

    # Build target datetime
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # If time has already passed today, set for tomorrow
    if target <= now:
        target += timedelta(days=1)

    call_time = target - timedelta(minutes=config.PREALARM_MINUTES)
    is_tomorrow = target.date() > now.date()

    alarm = alarm_manager.add_alarm(target, phone_number=phone)

    when = "tomorrow" if is_tomorrow else "today"
    mins_until = int((call_time - now).total_seconds() / 60)
    calling = phone or config.PHONE_NUMBER

    await interaction.response.send_message(
        f"⏰ **Alarm set!**\n"
        f"• Alarm time: **{target.strftime('%H:%M')}** {when}\n"
        f"• Calling: `+{calling}`\n"
        f"• I'll start calling at **{call_time.strftime('%H:%M')}** (5 mins early)\n"
        f"• That's in **{mins_until} minutes**\n"
        f"• ID: `alarm_{alarm.id}` (use this to cancel)"
    )


@alarm_group.command(name="list", description="List all active alarms")
async def alarm_list(interaction: discord.Interaction):
    active = alarm_manager.get_active_alarms()

    if not active:
        await interaction.response.send_message("No active alarms.", ephemeral=True)
        return

    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    lines = []

    for a in active:
        diff = a.target_time - now
        diff_mins = int(diff.total_seconds() / 60)

        status_icon = {
            AlarmStatus.PENDING: "⏳",
            AlarmStatus.RINGING: "🔔",
            AlarmStatus.DISMISSED: "✅",
            AlarmStatus.COMPLETED: "✔️",
        }.get(a.status, "?")

        extra = ""
        if a.status == AlarmStatus.RINGING:
            extra = f" (attempt #{a.retry_count})"
        elif a.status == AlarmStatus.DISMISSED:
            extra = f" ({a.follow_ups_remaining} follow-ups left)"

        lines.append(
            f"{status_icon} `alarm_{a.id}` — **{a.target_time.strftime('%H:%M')}** "
            f"(in {diff_mins}m){extra}"
        )

    await interaction.response.send_message("**Active alarms:**\n" + "\n".join(lines))


@alarm_group.command(name="cancel", description="Cancel an alarm")
@app_commands.describe(alarm_id="Alarm number (e.g. 1 for alarm_1)")
async def alarm_cancel(interaction: discord.Interaction, alarm_id: int):
    if alarm_manager.remove_alarm(alarm_id):
        await interaction.response.send_message(f"🗑️ Alarm `alarm_{alarm_id}` cancelled.")
    else:
        await interaction.response.send_message(
            f"❌ No alarm found with ID `alarm_{alarm_id}`.",
            ephemeral=True,
        )


@alarm_group.command(name="test", description="Immediately trigger a test call")
async def alarm_test(interaction: discord.Interaction):
    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    # Set alarm 6 minutes from now so it triggers in the next scheduler tick
    target = now + timedelta(minutes=6)

    alarm = alarm_manager.add_alarm(target)

    await interaction.response.send_message(
        f"🧪 **Test alarm created!**\n"
        f"You'll get a call in about 1 minute.\n"
        f"ID: `alarm_{alarm.id}`"
    )
