import re
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse

import config
from alarms import alarm_manager

app = FastAPI()


def _is_wake_phrase(text: str) -> bool:
    """Check if the transcript contains any wake keyword."""
    words = set(re.findall(r'\b\w+\b', text.lower()))
    return bool(words & set(config.WAKE_KEYWORDS))


@app.post("/speech")
async def speech_webhook(request: Request, alarm_id: int):
    """Vonage calls this with speech recognition results after the input action."""
    data = await request.json()

    # Check DTMF (any key press = dismissed)
    dtmf = data.get("dtmf", {})
    dtmf_tones = dtmf.get("tones", "")

    # Check speech
    speech = data.get("speech", {})
    results = speech.get("results", [])
    transcript = results[0].get("text", "").strip() if results else ""

    print(f"[Alarm {alarm_id}] DTMF: '{dtmf_tones}' | Speech: '{transcript}'")

    dismissed = False

    if dtmf_tones:
        dismissed = True
        print(f"[Alarm {alarm_id}] Dismissed via keypress")
    elif transcript and _is_wake_phrase(transcript):
        dismissed = True
        print(f"[Alarm {alarm_id}] Dismissed via speech: '{transcript}'")
    elif transcript:
        print(f"[Alarm {alarm_id}] Heard '{transcript}' — not a wake phrase, retrying")

    if dismissed:
        # Get call UUID from the event data
        call_uuid = data.get("uuid", data.get("call_uuid", ""))
        alarm_manager.dismiss_alarm(alarm_id, call_uuid)

        # Confirm to the user over the call
        return [{
            "action": "talk",
            "text": "Got it. Stay awake! I will check on you later.",
            "language": config.ALARM_LANGUAGE,
        }]

    # Not dismissed — let the call end, retry will be scheduled by event webhook
    return [{
        "action": "talk",
        "text": "You didn't respond. I will call again soon.",
        "language": config.ALARM_LANGUAGE,
    }]


@app.post("/event")
async def event_webhook(request: Request, alarm_id: int = None):
    """Vonage calls this for call status updates (started, answered, completed, etc.)."""
    data = await request.json()

    call_uuid = data.get("uuid", "")
    status = data.get("status", "")

    if alarm_id:
        print(f"[Alarm {alarm_id}] Event: status={status} uuid={call_uuid}")

        # When a call ends, update alarm state
        terminal_statuses = {"completed", "failed", "busy", "cancelled", "timeout", "unanswered", "rejected"}
        if status in terminal_statuses:
            alarm_manager.mark_call_complete(alarm_id, call_uuid, status)

    return {}


@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    """Serve audio files (MP3/WAV) for Vonage to stream."""
    # Security: only allow audio files
    allowed_extensions = {".mp3", ".wav", ".ogg", ".m4a"}
    path = Path(filename)

    if path.suffix.lower() not in allowed_extensions:
        raise HTTPException(status_code=403, detail="Only audio files allowed")

    file_path = Path(".") / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)


@app.get("/health")
async def health():
    """Health check endpoint."""
    active = alarm_manager.get_active_alarms()
    return {
        "status": "ok",
        "active_alarms": len(active),
        "alarms": [
            {
                "id": a.id,
                "target": a.target_time.isoformat(),
                "status": a.status.value,
                "retries": a.retry_count,
                "follow_ups": a.follow_ups_remaining,
            }
            for a in active
        ],
    }
