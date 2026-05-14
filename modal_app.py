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
from execution.claude_conversation import generate_reply_with_tools
from execution.elevenlabs_tts import synthesize_speech
from execution.google_calendar import book_appointment

# Tool schemas exposed to Claude via the Anthropic tool-use API.
# Claude decides when to call these based on caller intent.
TOOLS = [
    {
        "name": "book_appointment",
        "description": (
            "Book a discovery call on Harry's calendar after the caller has "
            "agreed on a specific date, time, and shared their name + email. "
            "Only call this after explicitly confirming the time back to "
            "the caller. Times are interpreted in America/Toronto (Eastern)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Caller's full name.",
                },
                "customer_email": {
                    "type": "string",
                    "description": (
                        "Caller's email address for the calendar invite. "
                        "Spell it back to the caller before booking to confirm."
                    ),
                },
                "start_iso": {
                    "type": "string",
                    "description": (
                        "Start time in ISO 8601 format without timezone, "
                        "e.g. '2026-05-15T14:00:00' for 2 PM. Local Eastern time."
                    ),
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Meeting length in minutes. Default 30.",
                    "default": 30,
                },
                "purpose": {
                    "type": "string",
                    "description": "Short summary of the meeting purpose.",
                    "default": "Discovery call",
                },
            },
            "required": ["customer_name", "customer_email", "start_iso"],
        },
    },
]


def dispatch_tool(name: str, tool_input: dict) -> dict:
    """Route a Claude tool_use call to the matching Python function."""
    if name == "book_appointment":
        return book_appointment(**tool_input)
    return {"status": "error", "error": f"unknown tool {name!r}"}

# ── Modal setup ──────────────────────────────────────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements("requirements.txt")
    .add_local_python_source("execution")
)

app = modal.App("ai-receptionist-phone")

# In-memory audio cache. Works because we pin the deployment to a single
# container (see ``max_containers=1`` on the @app.function decorator).
# That way the write in /voice/incoming and the read in /audio/{id} are
# guaranteed to hit the same Python process.
_AUDIO_MEMORY_CACHE: dict[str, bytes] = {}

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
    """Build the opening line the AI assistant says when a call comes in."""
    prefix = _time_of_day_greeting(config["timezone"])
    return (
        f"{prefix}. I'm {config['ai_name']}, {config['ai_role']}. "
        f"How can I help you?"
    )

# ── FastAPI app ──────────────────────────────────────────────────────────
api = FastAPI(title="AI Receptionist Phone MVP")


class InMemoryAudioStorage:
    """Production audio storage backed by a Python dict in the container.

    Implements the same ``save`` / ``load`` interface as
    ``execution.audio_storage.AudioStorage``. Works only because the
    deployment is pinned to a single container (max_containers=1) — so
    every request hits the same Python process and sees the same dict.
    """

    def save(self, mp3_bytes: bytes) -> str:
        import uuid
        audio_id = str(uuid.uuid4())
        _AUDIO_MEMORY_CACHE[audio_id] = mp3_bytes
        return audio_id

    def load(self, audio_id: str) -> bytes | None:
        return _AUDIO_MEMORY_CACHE.get(audio_id)


def get_storage():
    """Dependency injection for audio storage.

    Production: returns the in-memory storage (single-container deploy).
    Tests: overridden via ``api.dependency_overrides[get_storage]`` to use
    the file-based ``AudioStorage`` for hermetic tmp_path tests.
    """
    return InMemoryAudioStorage()


async def validate_twilio(request: Request) -> None:
    """FastAPI dependency: reject requests not signed by Twilio.

    Without this, anyone who finds the public Modal URL could hammer
    /voice/incoming and burn through ElevenLabs/Claude credits.

    Modal terminates TLS upstream, so ``request.url`` inside the container
    shows ``http://`` but Twilio signed against the public ``https://`` URL.
    We reconstruct the URL Twilio actually called using ``PUBLIC_BASE_URL``.

    Tests override this via ``api.dependency_overrides[validate_twilio]``.
    Set ``TWILIO_SKIP_VALIDATION=true`` to bypass at runtime (dev only) —
    validation is still computed and logged so we can debug mismatches.
    """
    bypass = os.environ.get("TWILIO_SKIP_VALIDATION") == "true"

    validator = RequestValidator(os.environ["TWILIO_AUTH_TOKEN"])
    signature = request.headers.get("X-Twilio-Signature", "")
    form_data = await request.form()
    form_dict = dict(form_data)

    # Twilio adds these params to the request AFTER computing the signature,
    # so they must be excluded from our verification or validation fails.
    # CallToken: documented exclusion (call-resource docs).
    # StirVerstat: STIR/SHAKEN attestation info added by Twilio's voice
    #   infrastructure after the webhook is signed. Verified empirically
    #   in our logs — every failure included this param.
    for hidden_param in ("CallToken", "StirVerstat"):
        form_dict.pop(hidden_param, None)

    public_base = os.environ["PUBLIC_BASE_URL"].rstrip("/")
    url = f"{public_base}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    is_valid = validator.validate(url, form_dict, signature)

    if not is_valid:
        # Compute what we think the signature should be, so we can compare
        # to what Twilio sent. If they don't match, either the token is wrong
        # or one of url/params doesn't match Twilio's view.
        computed = validator.compute_signature(url, form_dict)
        token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        token_fingerprint = f"{token[:4]}...{token[-4:]}" if len(token) >= 8 else "(too short)"
        print(
            "[twilio-validation] FAIL "
            f"url={url!r} "
            f"sig_received={signature!r} "
            f"sig_computed={computed!r} "
            f"token_fingerprint={token_fingerprint} "
            f"form_keys={sorted(form_dict.keys())!r}"
        )
        if not bypass:
            raise HTTPException(status_code=403, detail="invalid twilio signature")
    else:
        print(f"[twilio-validation] OK url={url!r}")


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
        f'speechTimeout="auto" timeout="12"></Gather>'
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
            f'speechTimeout="auto" timeout="12"></Gather>'
            f'<Redirect>/voice/incoming</Redirect>'
        )

    # Get prior history (or start fresh if Twilio retried after restart)
    history = CONVERSATIONS.get(CallSid, [])
    system_prompt = build_system_prompt(config)

    # Generate reply. ``generate_reply_with_tools`` may invoke tools
    # (e.g. book_appointment) mid-turn; the returned ``updated_history``
    # already includes the new user message + any tool round-trips +
    # the final assistant reply.
    reply_text, updated_history = generate_reply_with_tools(
        system_prompt=system_prompt,
        history=history,
        new_message=SpeechResult,
        tools=TOOLS,
        tool_dispatcher=dispatch_tool,
    )

    CONVERSATIONS[CallSid] = updated_history

    # TTS + return TwiML
    audio_id = storage.save(synthesize_speech(reply_text))
    audio_url = _public_audio_url(audio_id)
    return _twiml(
        f"<Play>{audio_url}</Play>"
        f'<Gather input="speech" action="/voice/gather" method="POST" '
        f'speechTimeout="auto" timeout="12"></Gather>'
        # If caller goes silent, hang up gracefully
        f'<Say>Thank you for calling. Goodbye.</Say>'
        f'<Hangup/>'
    )


# ── Modal deployment hook ────────────────────────────────────────────────
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("ai-receptionist-secrets")],
    min_containers=1,        # keep warm to reduce phone latency
    max_containers=1,        # pin to ONE container so /audio/{id} hits the same process that wrote it
)
@modal.concurrent(max_inputs=20)  # allow 20 concurrent requests in this one container
@modal.asgi_app()
def fastapi_app():
    return api
