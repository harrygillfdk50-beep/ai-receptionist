"""FastAPI app deployed on Modal — Twilio voice webhooks + audio playback."""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import modal
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from twilio.request_validator import RequestValidator

from execution.audio_storage import AudioStorage

from fastapi import Form
from fastapi.responses import Response as FastAPIResponse

from execution.business_config import get_business_config, build_system_prompt
from execution.claude_conversation import generate_reply
from execution.elevenlabs_tts import synthesize_speech

# ── Modal setup ──────────────────────────────────────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements("requirements.txt")
    .add_local_python_source("execution")
)

app = modal.App("ai-receptionist-phone")

# Cross-container shared storage for short-lived TTS audio.
# Modal Volumes have write-back caching that isn't visible to other
# containers without explicit commit/reload; modal.Dict avoids that
# entirely — writes are immediately visible everywhere.
AUDIO_DICT = modal.Dict.from_name("ai-receptionist-audio-cache", create_if_missing=True)

# In-memory conversation store keyed by Twilio CallSid.
# Phase 5 replaces this with Supabase. Fine for single-process Phase 1 MVP.
CONVERSATIONS: dict[str, list[dict]] = {}


def _time_of_day_greeting(timezone: str) -> str:
    """Return 'Good morning', 'Good afternoon', 'Good evening', or 'Hello'
    based on the current hour in the given IANA timezone.
    """
    hour = datetime.now(ZoneInfo(timezone)).hour
    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 17:
        return "Good afternoon"
    if 17 <= hour < 22:
        return "Good evening"
    return "Hello"


def build_greeting(config: dict) -> str:
    """Build the opening line Maya says when a call comes in."""
    prefix = _time_of_day_greeting(config["timezone"])
    return (
        f"{prefix}. I'm {config['ai_name']}, {config['ai_role']}. "
        f"How can I help you?"
    )

# ── FastAPI app ──────────────────────────────────────────────────────────
api = FastAPI(title="AI Receptionist Phone MVP")


class ModalDictAudioStorage:
    """Production audio storage backed by modal.Dict.

    Implements the same ``save`` / ``load`` interface as
    ``execution.audio_storage.AudioStorage`` but stores bytes in a
    cross-container shared Modal Dict instead of files on a Volume.

    Why: Modal scales the web app across containers. With volumes, a write
    in container A is not visible to container B until commit/reload.
    modal.Dict makes writes immediately visible everywhere.
    """

    def save(self, mp3_bytes: bytes) -> str:
        import uuid
        audio_id = str(uuid.uuid4())
        AUDIO_DICT[audio_id] = mp3_bytes
        return audio_id

    def load(self, audio_id: str) -> bytes | None:
        return AUDIO_DICT.get(audio_id)


def get_storage():
    """Dependency injection for audio storage.

    Production: returns the modal.Dict-backed storage.
    Tests: overridden via ``api.dependency_overrides[get_storage]`` to use
    the file-based ``AudioStorage`` for hermetic tmp_path tests.
    """
    return ModalDictAudioStorage()


async def validate_twilio(request: Request) -> None:
    """FastAPI dependency: reject requests not signed by Twilio.

    Without this, anyone who finds the public Modal URL could hammer
    /voice/incoming and burn through ElevenLabs/Claude credits.

    Modal terminates TLS upstream, so ``request.url`` inside the container
    shows ``http://`` but Twilio signed against the public ``https://`` URL.
    We reconstruct the URL Twilio actually called using ``PUBLIC_BASE_URL``.

    Tests override this via ``api.dependency_overrides[validate_twilio]``.
    Set ``TWILIO_SKIP_VALIDATION=true`` to bypass at runtime (dev only).
    """
    if os.environ.get("TWILIO_SKIP_VALIDATION") == "true":
        return

    validator = RequestValidator(os.environ["TWILIO_AUTH_TOKEN"])
    signature = request.headers.get("X-Twilio-Signature", "")
    form_data = await request.form()

    # Rebuild the public URL Twilio used. Path + (optional) query string.
    public_base = os.environ["PUBLIC_BASE_URL"].rstrip("/")
    url = f"{public_base}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    if not validator.validate(url, dict(form_data), signature):
        raise HTTPException(status_code=403, detail="invalid twilio signature")


@api.get("/audio/{audio_id}")
def get_audio(audio_id: str, storage: AudioStorage = Depends(get_storage)):
    audio = storage.load(audio_id)
    if audio is None:
        raise HTTPException(status_code=404, detail="audio not found")
    return Response(content=audio, media_type="audio/mpeg")


def _public_audio_url(audio_id: str) -> str:
    base = os.environ["PUBLIC_BASE_URL"].rstrip("/")
    return f"{base}/audio/{audio_id}"


def _twiml(body: str) -> FastAPIResponse:
    return FastAPIResponse(
        content=f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>',
        media_type="application/xml",
    )


@api.post("/voice/incoming", dependencies=[Depends(validate_twilio)])
def voice_incoming(
    CallSid: str = Form(...),
    From: str = Form(...),
    storage: AudioStorage = Depends(get_storage),
):
    config = get_business_config()
    greeting = build_greeting(config)

    # Synthesize greeting and store
    audio_bytes = synthesize_speech(greeting)
    audio_id = storage.save(audio_bytes)

    # Initialize conversation history
    CONVERSATIONS[CallSid] = [{"role": "assistant", "content": greeting}]

    audio_url = _public_audio_url(audio_id)
    twiml_body = (
        f"<Play>{audio_url}</Play>"
        f'<Gather input="speech" action="/voice/gather" method="POST" '
        f'speechTimeout="auto" timeout="5"></Gather>'
        # Fallback if no speech captured: redirect back to incoming
        f'<Redirect>/voice/incoming</Redirect>'
    )
    return _twiml(twiml_body)


REPROMPT_TEXT = "I didn't catch that. Could you say it again?"


@api.post("/voice/gather", dependencies=[Depends(validate_twilio)])
def voice_gather(
    CallSid: str = Form(...),
    SpeechResult: str = Form(""),
    storage: AudioStorage = Depends(get_storage),
):
    config = get_business_config()

    # No speech captured: re-prompt and gather again.
    if not SpeechResult.strip():
        audio_id = storage.save(synthesize_speech(REPROMPT_TEXT))
        audio_url = _public_audio_url(audio_id)
        return _twiml(
            f"<Play>{audio_url}</Play>"
            f'<Gather input="speech" action="/voice/gather" method="POST" '
            f'speechTimeout="auto" timeout="5"></Gather>'
            f'<Redirect>/voice/incoming</Redirect>'
        )

    # Get prior history (or start fresh if Twilio retried after restart)
    history = CONVERSATIONS.get(CallSid, [])
    system_prompt = build_system_prompt(config)

    # Generate reply
    reply_text = generate_reply(
        system_prompt=system_prompt,
        history=history,
        new_message=SpeechResult,
    )

    # Update history
    CONVERSATIONS[CallSid] = history + [
        {"role": "user", "content": SpeechResult},
        {"role": "assistant", "content": reply_text},
    ]

    # TTS + return TwiML
    audio_id = storage.save(synthesize_speech(reply_text))
    audio_url = _public_audio_url(audio_id)
    return _twiml(
        f"<Play>{audio_url}</Play>"
        f'<Gather input="speech" action="/voice/gather" method="POST" '
        f'speechTimeout="auto" timeout="5"></Gather>'
        # If caller goes silent, hang up gracefully
        f'<Say>Thank you for calling. Goodbye.</Say>'
        f'<Hangup/>'
    )


# ── Modal deployment hook ────────────────────────────────────────────────
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("ai-receptionist-secrets")],
    min_containers=1,  # keep warm to reduce phone latency
)
@modal.asgi_app()
def fastapi_app():
    return api
