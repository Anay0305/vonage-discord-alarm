import asyncio
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict
import jwt
import httpx
from zoneinfo import ZoneInfo

import config


class AlarmStatus(Enum):
    PENDING = "pending"
    RINGING = "ringing"
    DISMISSED = "dismissed"
    COMPLETED = "completed"


@dataclass
class Alarm:
    id: int
    target_time: datetime
    phone_number: str
    status: AlarmStatus = AlarmStatus.PENDING

    # Call tracking
    active_call_uuid: Optional[str] = None
    retry_count: int = 0
    next_call_time: Optional[datetime] = None

    # Follow-up tracking
    follow_ups_remaining: int = config.FOLLOW_UP_COUNT
    is_follow_up: bool = False


class AlarmManager:
    def __init__(self):
        self.alarms: Dict[int, Alarm] = {}
        self.next_id = 1
        self.discord_bot = None  # Injected later
        self._scheduler_task = None

    def set_discord_bot(self, bot):
        """Inject Discord bot for notifications."""
        self.discord_bot = bot

    async def start_scheduler(self):
        """Background task that checks alarms and triggers calls."""
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop_scheduler(self):
        """Stop the scheduler."""
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

    async def _scheduler_loop(self):
        """Check alarms every 10 seconds."""
        while True:
            try:
                await asyncio.sleep(10)
                await self._check_alarms()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Scheduler error: {e}")

    async def _check_alarms(self):
        """Check if any alarms need to ring."""
        now = datetime.now(ZoneInfo(config.TIMEZONE))

        for alarm in list(self.alarms.values()):
            # Skip completed alarms
            if alarm.status == AlarmStatus.COMPLETED:
                continue

            # Skip if call already in progress
            if alarm.active_call_uuid:
                continue

            # Check if it's time to call
            should_call = False

            if alarm.status == AlarmStatus.PENDING:
                # Initial alarm: call X minutes before target time
                call_time = alarm.target_time - timedelta(minutes=config.PREALARM_MINUTES)
                if now >= call_time:
                    should_call = True
                    alarm.status = AlarmStatus.RINGING

            elif alarm.status == AlarmStatus.RINGING:
                # Retry logic for unanswered/no-response
                if alarm.next_call_time and now >= alarm.next_call_time:
                    if alarm.retry_count >= config.MAX_RETRIES:
                        print(f"⏰ Alarm {alarm.id} exceeded max retries. Giving up.")
                        alarm.status = AlarmStatus.COMPLETED
                        continue
                    should_call = True

            elif alarm.status == AlarmStatus.DISMISSED:
                # Follow-up calls after dismissal
                if alarm.follow_ups_remaining > 0:
                    if alarm.next_call_time and now >= alarm.next_call_time:
                        should_call = True
                        alarm.is_follow_up = True
                else:
                    # All follow-ups done
                    alarm.status = AlarmStatus.COMPLETED
                    print(f"✅ Alarm {alarm.id} completed (all follow-ups done)")

            if should_call:
                await self._make_call(alarm)

    async def _make_call(self, alarm: Alarm):
        """Initiate a Vonage call."""
        try:
            print(f"📞 Making call for alarm {alarm.id} (retry {alarm.retry_count})")

            # Generate JWT
            jwt_token = self._generate_jwt()
            if not jwt_token:
                print(f"❌ Failed to generate JWT for alarm {alarm.id}")
                return

            # Build NCCO
            ncco = self._build_ncco(alarm)

            # Make call
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.nexmo.com/v1/calls",
                    headers={
                        "Authorization": f"Bearer {jwt_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "to": [{"type": "phone", "number": alarm.phone_number}],
                        "from": {"type": "phone", "number": config.VONAGE_FROM_NUMBER},
                        "ncco": ncco,
                        "event_url": [f"{config.WEBHOOK_BASE_URL}/event?alarm_id={alarm.id}"],
                        "ringing_timer": config.CALL_RINGING_TIMEOUT,
                        "length_timer": config.CALL_MAX_DURATION,
                    }
                )

                if response.status_code == 201:
                    result = response.json()
                    call_uuid = result.get("uuid")
                    alarm.active_call_uuid = call_uuid
                    alarm.retry_count += 1
                    print(f"✅ Call initiated: {call_uuid}")
                else:
                    print(f"❌ Call failed: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"❌ Error making call for alarm {alarm.id}: {e}")

    def _build_ncco(self, alarm: Alarm) -> list:
        """Build NCCO for the call."""
        ncco = []

        # Check if we have a local MP3 file
        audio_file = Path(config.ALARM_AUDIO_FILE)

        if audio_file.exists():
            # Stream the MP3 file
            audio_url = f"{config.WEBHOOK_BASE_URL}/audio/{config.ALARM_AUDIO_FILE}"
            ncco.append({
                "action": "stream",
                "streamUrl": [audio_url],
                "loop": 5,  # Play 5 times
                "bargeIn": True,
            })
        else:
            # Fallback to TTS
            text = config.FOLLOWUP_TTS_TEXT if alarm.is_follow_up else config.ALARM_TTS_TEXT
            ncco.append({
                "action": "talk",
                "text": text,
                "language": config.ALARM_LANGUAGE,
                "loop": 5,
                "bargeIn": True,
            })

        # Listen for speech or DTMF
        ncco.append({
            "action": "input",
            "type": ["speech", "dtmf"],
            "speech": {
                "language": config.ALARM_LANGUAGE,
                "endOnSilence": 2,
                "maxDuration": 10,
            },
            "dtmf": {
                "maxDigits": 1,
            },
            "eventUrl": [f"{config.WEBHOOK_BASE_URL}/speech?alarm_id={alarm.id}"],
        })

        return ncco

    def _generate_jwt(self) -> Optional[str]:
        """Generate JWT for Vonage API."""
        try:
            private_key = Path(config.VONAGE_PRIVATE_KEY_PATH).read_text()
            now = int(time.time())
            payload = {
                "application_id": config.VONAGE_APPLICATION_ID,
                "iat": now,
                "exp": now + 300,
                "jti": f"alarm-{now}"
            }
            return jwt.encode(payload, private_key, algorithm="RS256")
        except Exception as e:
            print(f"❌ JWT generation failed: {e}")
            return None

    def add_alarm(self, target_time: datetime, phone_number: Optional[str] = None) -> Alarm:
        """Create a new alarm. Uses config.PHONE_NUMBER if phone_number not given."""
        alarm = Alarm(
            id=self.next_id,
            target_time=target_time,
            phone_number=phone_number or config.PHONE_NUMBER,
        )
        self.alarms[alarm.id] = alarm
        self.next_id += 1
        print(f"✅ Created alarm {alarm.id} for {target_time}")
        return alarm

    def remove_alarm(self, alarm_id: int) -> bool:
        """Cancel an alarm."""
        if alarm_id in self.alarms:
            del self.alarms[alarm_id]
            print(f"🗑️ Removed alarm {alarm_id}")
            return True
        return False

    def get_active_alarms(self):
        """Get all non-completed alarms."""
        return [a for a in self.alarms.values() if a.status != AlarmStatus.COMPLETED]

    def mark_call_complete(self, alarm_id: int, call_uuid: str, status: str):
        """Called when a call ends (from webhook)."""
        alarm = self.alarms.get(alarm_id)
        if not alarm or alarm.active_call_uuid != call_uuid:
            return

        print(f"📞 Call {call_uuid} ended with status: {status}")
        alarm.active_call_uuid = None

        # If dismissed, don't schedule retry
        if alarm.status == AlarmStatus.DISMISSED:
            return

        # Schedule retry for unanswered/failed calls
        if status in ["unanswered", "failed", "timeout", "busy", "rejected"]:
            alarm.next_call_time = datetime.now(ZoneInfo(config.TIMEZONE)) + timedelta(
                seconds=config.RETRY_INTERVAL_SECONDS
            )
            print(f"⏰ Retry scheduled for alarm {alarm_id} at {alarm.next_call_time}")

    def dismiss_alarm(self, alarm_id: int, call_uuid: str):
        """Mark alarm as dismissed and schedule follow-ups."""
        alarm = self.alarms.get(alarm_id)
        if not alarm:
            return

        print(f"✅ Alarm {alarm_id} dismissed by user")

        # Clear active call
        alarm.active_call_uuid = None

        if alarm.is_follow_up:
            # Follow-up was acknowledged
            alarm.follow_ups_remaining -= 1
            print(f"✅ Follow-up acknowledged. {alarm.follow_ups_remaining} remaining.")
            alarm.is_follow_up = False
        else:
            # Main alarm dismissed
            alarm.status = AlarmStatus.DISMISSED

        # Schedule next follow-up
        if alarm.follow_ups_remaining > 0:
            delay = random.randint(config.FOLLOW_UP_MIN_SECONDS, config.FOLLOW_UP_MAX_SECONDS)
            alarm.next_call_time = datetime.now(ZoneInfo(config.TIMEZONE)) + timedelta(seconds=delay)
            print(f"⏰ Follow-up scheduled in {delay}s at {alarm.next_call_time}")
        else:
            alarm.status = AlarmStatus.COMPLETED
            print(f"🎉 Alarm {alarm_id} fully completed")


# Global instance
alarm_manager = AlarmManager()
