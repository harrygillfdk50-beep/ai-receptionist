"""FastAPI app deployed on Modal — Twilio voice webhooks + audio playback."""

import os
import modal
from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse

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
volume = modal.Volume.from_name("ai-receptionist-audio", create_if_missing=True)

AUDIO_DIR = "/audio_volume"

# In-memory conversation store keyed by Twilio CallSid.
# Phase 5 replaces this with Supabase. Fine for single-process Phase 1 MVP.
CONVERSATIONS: dict[str, list[dict]] = {}

GREETING_TEMPLATE = "Thank you for calling {name}. How can I help you today?"

# ── FastAPI app ──────────────────────────────────────────────────────────
api = FastAPI(title="AI Receptionist Phone MVP")


def get_storage() -> AudioStorage:
    """Dependency injection for AudioStorage."""
    return AudioStorage(base_dir=AUDIO_DIR)


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


@api.post("/voice/incoming")
def voice_incoming(
    CallSid: str = Form(...),
    From: str = Form(...),
    storage: AudioStorage = Depends(get_storage),
):
    config = get_business_config()
    greeting = GREETING_TEMPLATE.format(name=config["name"])

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


# ── Modal deployment hook ────────────────────────────────────────────────
@app.function(
    image=image,
    volumes={AUDIO_DIR: volume},
    secrets=[modal.Secret.from_name("ai-receptionist-secrets")],
    min_containers=1,  # keep warm to reduce phone latency
)
@modal.asgi_app()
def fastapi_app():
    return api
