"""FastAPI app deployed on Modal — Twilio voice webhooks + audio playback."""

import os
import modal
from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse

from execution.audio_storage import AudioStorage

# ── Modal setup ──────────────────────────────────────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements("requirements.txt")
    .add_local_python_source("execution")
)

app = modal.App("ai-receptionist-phone")
volume = modal.Volume.from_name("ai-receptionist-audio", create_if_missing=True)

AUDIO_DIR = "/audio_volume"

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
