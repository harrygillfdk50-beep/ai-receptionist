# Phase 1: Phone Call MVP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a phone-only AI receptionist for a single hardcoded business: caller dials a Twilio number, gets greeted by an AI voice (ElevenLabs), can have a multi-turn conversation powered by Claude, and the AI responds in natural-sounding voice.

**Architecture:** FastAPI app deployed on Modal handles Twilio voice webhooks. `<Gather input="speech">` does STT and POSTs the transcript to our action endpoint. Claude generates the reply, ElevenLabs converts it to MP3, the MP3 is stored on a Modal Volume and served via a public endpoint, and TwiML's `<Play>` tells Twilio to play it. Loop until caller hangs up.

**Tech Stack:** Python 3.11, FastAPI, Modal, Twilio (Voice + Speech recognition), ElevenLabs API, Anthropic Claude API (Sonnet 4.5), pytest.

**Out of scope for Phase 1:** Multi-tenant config, Supabase, chat widget, Google Calendar booking, human transfer, SMS/email follow-ups, dashboard. All those land in later phases.

---

## File Structure

```
ai-receptionist/
├── execution/
│   ├── __init__.py
│   ├── business_config.py        # hardcoded business (name, hours, FAQs, prompt)
│   ├── claude_conversation.py    # Claude API wrapper with conversation memory
│   ├── elevenlabs_tts.py         # ElevenLabs TTS → MP3 bytes
│   └── audio_storage.py          # save MP3, return ID; load MP3 by ID
├── tests/
│   ├── __init__.py
│   ├── test_business_config.py
│   ├── test_claude_conversation.py
│   ├── test_elevenlabs_tts.py
│   ├── test_audio_storage.py
│   └── test_modal_app.py
├── modal_app.py                  # FastAPI on Modal: Twilio webhooks + audio endpoint
├── requirements.txt
├── pytest.ini
└── .env.example
```

**Responsibility per file:**
- `business_config.py` — single source of truth for the test business; returns dict with name, system prompt, etc.
- `claude_conversation.py` — given message history + new message + system prompt, returns Claude's reply text.
- `elevenlabs_tts.py` — given text, returns MP3 bytes.
- `audio_storage.py` — persists MP3 bytes with a UUID key, retrieves by key.
- `modal_app.py` — three HTTP endpoints: `/voice/incoming`, `/voice/gather`, `/audio/{audio_id}`.

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `.env.example`
- Create: `execution/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `requirements.txt`**

```
modal==0.64.0
fastapi==0.110.0
anthropic==0.39.0
elevenlabs==1.7.0
twilio==9.0.0
python-dotenv==1.0.1
pytest==8.0.0
pytest-asyncio==0.23.0
httpx==0.27.0
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
python_files = test_*.py
python_functions = test_*
```

- [ ] **Step 3: Create `.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-xxx
ELEVENLABS_API_KEY=xxx
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_PHONE_NUMBER=+15555550000
PUBLIC_BASE_URL=https://your-modal-app.modal.run
```

- [ ] **Step 4: Create empty `__init__.py` files**

```bash
touch execution/__init__.py tests/__init__.py
```

- [ ] **Step 5: Set up Python venv and install deps**

```bash
cd "d:/Automations/ai-receptionist"
python -m venv venv
source venv/Scripts/activate    # Windows Git Bash
pip install -r requirements.txt
```

Expected: All packages install without errors.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini .env.example execution/__init__.py tests/__init__.py
git commit -m "chore: project setup — deps, pytest config, env template"
```

---

## Task 2: Business Config Module

**Files:**
- Create: `execution/business_config.py`
- Test: `tests/test_business_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_business_config.py`:

```python
from execution.business_config import get_business_config, build_system_prompt


def test_get_business_config_returns_required_fields():
    config = get_business_config()
    assert config["name"]
    assert config["business_type"]
    assert isinstance(config["hours"], dict)
    assert isinstance(config["services"], list)
    assert isinstance(config["faqs"], list)
    assert config["tone"] in ("friendly", "professional", "casual")


def test_build_system_prompt_includes_business_name():
    config = get_business_config()
    prompt = build_system_prompt(config)
    assert config["name"] in prompt


def test_build_system_prompt_includes_hours_and_services():
    config = get_business_config()
    prompt = build_system_prompt(config)
    for service in config["services"]:
        assert service in prompt
    assert "hours" in prompt.lower() or "open" in prompt.lower()


def test_build_system_prompt_instructs_short_replies_for_phone():
    config = get_business_config()
    prompt = build_system_prompt(config)
    assert "short" in prompt.lower() or "brief" in prompt.lower() or "concise" in prompt.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_business_config.py -v
```

Expected: All 4 tests FAIL with `ImportError` or `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`execution/business_config.py`:

```python
"""Hardcoded test business config for Phase 1 MVP.

In Phase 5, this will be replaced by a Supabase lookup keyed by phone number.
"""


def get_business_config() -> dict:
    return {
        "name": "Bright Smile Dental",
        "business_type": "dental clinic",
        "hours": {
            "monday": "9:00-17:00",
            "tuesday": "9:00-17:00",
            "wednesday": "9:00-17:00",
            "thursday": "9:00-19:00",
            "friday": "9:00-15:00",
            "saturday": "closed",
            "sunday": "closed",
        },
        "services": [
            "Routine cleaning",
            "Cavity filling",
            "Teeth whitening",
            "Emergency dental care",
        ],
        "faqs": [
            {"q": "Do you accept insurance?", "a": "Yes, we accept most major dental insurance plans including Delta, Cigna, and Aetna."},
            {"q": "Where are you located?", "a": "We're at 123 Main Street, Springfield."},
            {"q": "Do you treat children?", "a": "Yes, we welcome patients of all ages."},
        ],
        "tone": "friendly",
        "owner_phone": "+15555550100",
    }


def build_system_prompt(config: dict) -> str:
    hours_lines = "\n".join(f"  {day.title()}: {h}" for day, h in config["hours"].items())
    services_lines = "\n".join(f"  - {s}" for s in config["services"])
    faqs_lines = "\n".join(f"  Q: {f['q']}\n  A: {f['a']}" for f in config["faqs"])

    return f"""You are the AI receptionist for {config['name']}, a {config['business_type']}.

Your tone is {config['tone']}.

Hours:
{hours_lines}

Services:
{services_lines}

Knowledge Base (FAQs):
{faqs_lines}

Rules:
- This is a phone call, so keep every reply SHORT and CONCISE — ideally one or two sentences.
- Never make up information not in the FAQs or services list. If unsure, say you'll have someone call them back.
- Speak naturally, like a real receptionist. Don't say "as an AI".
- Greet the caller warmly when the call starts.
"""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_business_config.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/business_config.py tests/test_business_config.py
git commit -m "feat: hardcoded business config + system prompt builder"
```

---

## Task 3: Claude Conversation Module

**Files:**
- Create: `execution/claude_conversation.py`
- Test: `tests/test_claude_conversation.py`

- [ ] **Step 1: Write the failing test**

`tests/test_claude_conversation.py`:

```python
from unittest.mock import MagicMock, patch
from execution.claude_conversation import generate_reply


@patch("execution.claude_conversation.Anthropic")
def test_generate_reply_returns_assistant_text(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Hello! How can I help you today?")]
    )

    reply = generate_reply(
        system_prompt="You are a receptionist.",
        history=[],
        new_message="Hi",
    )

    assert reply == "Hello! How can I help you today?"


@patch("execution.claude_conversation.Anthropic")
def test_generate_reply_passes_history_to_claude(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Sure, what time?")]
    )

    history = [
        {"role": "user", "content": "I want to book an appointment."},
        {"role": "assistant", "content": "Of course! What day works for you?"},
    ]
    generate_reply(
        system_prompt="You are a receptionist.",
        history=history,
        new_message="Tomorrow",
    )

    call_args = mock_client.messages.create.call_args
    messages = call_args.kwargs["messages"]
    # history (2) + new user message (1) = 3
    assert len(messages) == 3
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["content"] == "Tomorrow"


@patch("execution.claude_conversation.Anthropic")
def test_generate_reply_uses_sonnet_4_5_model(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="ok")]
    )

    generate_reply(system_prompt="x", history=[], new_message="y")

    model = mock_client.messages.create.call_args.kwargs["model"]
    assert "claude" in model
    assert "sonnet" in model
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_claude_conversation.py -v
```

Expected: All 3 tests FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

`execution/claude_conversation.py`:

```python
"""Claude API wrapper for the receptionist conversation engine."""

import os
from anthropic import Anthropic

CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 300  # phone replies should be short


def generate_reply(
    system_prompt: str,
    history: list[dict],
    new_message: str,
) -> str:
    """Generate an assistant reply.

    Args:
        system_prompt: The business-specific system prompt.
        history: List of {"role": "user"|"assistant", "content": str} dicts.
        new_message: The latest user message (caller's transcribed speech).

    Returns:
        The assistant's reply text.
    """
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages = list(history) + [{"role": "user", "content": new_message}]

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )

    return response.content[0].text
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_claude_conversation.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/claude_conversation.py tests/test_claude_conversation.py
git commit -m "feat: Claude conversation wrapper with history support"
```

---

## Task 4: ElevenLabs TTS Module

**Files:**
- Create: `execution/elevenlabs_tts.py`
- Test: `tests/test_elevenlabs_tts.py`

- [ ] **Step 1: Write the failing test**

`tests/test_elevenlabs_tts.py`:

```python
from unittest.mock import MagicMock, patch
from execution.elevenlabs_tts import synthesize_speech


@patch("execution.elevenlabs_tts.ElevenLabs")
def test_synthesize_speech_returns_bytes(mock_eleven_cls):
    mock_client = MagicMock()
    mock_eleven_cls.return_value = mock_client
    mock_client.text_to_speech.convert.return_value = iter([b"fake_mp3_chunk_1", b"fake_mp3_chunk_2"])

    audio = synthesize_speech("Hello there!")

    assert isinstance(audio, bytes)
    assert audio == b"fake_mp3_chunk_1fake_mp3_chunk_2"


@patch("execution.elevenlabs_tts.ElevenLabs")
def test_synthesize_speech_uses_configured_voice_id(mock_eleven_cls, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test_voice_xyz")
    mock_client = MagicMock()
    mock_eleven_cls.return_value = mock_client
    mock_client.text_to_speech.convert.return_value = iter([b"x"])

    synthesize_speech("Hello")

    call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
    assert call_kwargs["voice_id"] == "test_voice_xyz"


@patch("execution.elevenlabs_tts.ElevenLabs")
def test_synthesize_speech_requests_mp3_format(mock_eleven_cls):
    mock_client = MagicMock()
    mock_eleven_cls.return_value = mock_client
    mock_client.text_to_speech.convert.return_value = iter([b"x"])

    synthesize_speech("Hello")

    call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
    assert "mp3" in call_kwargs["output_format"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_elevenlabs_tts.py -v
```

Expected: All 3 tests FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

`execution/elevenlabs_tts.py`:

```python
"""ElevenLabs text-to-speech wrapper.

Returns MP3 bytes. Twilio's <Play> verb supports MP3 over HTTPS, so we serve
these bytes from `modal_app.py`'s /audio/{id} endpoint.
"""

import os
from elevenlabs.client import ElevenLabs

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs "Rachel"
DEFAULT_MODEL = "eleven_turbo_v2_5"  # low-latency, good for phone
OUTPUT_FORMAT = "mp3_22050_32"  # 22kHz mono — small + fast, good enough for phone


def synthesize_speech(text: str) -> bytes:
    """Convert text to MP3 audio bytes via ElevenLabs.

    Args:
        text: The string to speak.

    Returns:
        Raw MP3 bytes.
    """
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)

    audio_stream = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=DEFAULT_MODEL,
        output_format=OUTPUT_FORMAT,
    )

    return b"".join(audio_stream)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_elevenlabs_tts.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/elevenlabs_tts.py tests/test_elevenlabs_tts.py
git commit -m "feat: ElevenLabs TTS wrapper returning MP3 bytes"
```

---

## Task 5: Audio Storage Module

**Files:**
- Create: `execution/audio_storage.py`
- Test: `tests/test_audio_storage.py`

Twilio's `<Play>` requires a publicly accessible URL. We'll store MP3 bytes in a local directory (later replaced by a Modal Volume). Each clip gets a UUID. The `modal_app.py` `/audio/{id}` endpoint reads from this storage and streams the file.

- [ ] **Step 1: Write the failing test**

`tests/test_audio_storage.py`:

```python
import uuid
from pathlib import Path
from execution.audio_storage import AudioStorage


def test_save_returns_uuid_string(tmp_path):
    store = AudioStorage(base_dir=tmp_path)
    audio_id = store.save(b"fake_mp3_data")
    assert isinstance(audio_id, str)
    # Should parse as a UUID
    uuid.UUID(audio_id)


def test_save_then_load_returns_same_bytes(tmp_path):
    store = AudioStorage(base_dir=tmp_path)
    payload = b"\xff\xfb\x90hello mp3"
    audio_id = store.save(payload)

    loaded = store.load(audio_id)

    assert loaded == payload


def test_load_unknown_id_returns_none(tmp_path):
    store = AudioStorage(base_dir=tmp_path)
    assert store.load("not-a-real-id") is None


def test_save_creates_file_in_base_dir(tmp_path):
    store = AudioStorage(base_dir=tmp_path)
    audio_id = store.save(b"data")

    files = list(Path(tmp_path).iterdir())
    assert len(files) == 1
    assert audio_id in files[0].name
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_audio_storage.py -v
```

Expected: All 4 tests FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

`execution/audio_storage.py`:

```python
"""Audio file storage for Twilio playback.

Saves MP3 bytes to disk under a UUID key. In production (Modal), `base_dir`
points to a Modal Volume so storage persists across container restarts.
"""

import uuid
from pathlib import Path


class AudioStorage:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, mp3_bytes: bytes) -> str:
        """Save MP3 bytes; return the audio_id (UUID string)."""
        audio_id = str(uuid.uuid4())
        path = self.base_dir / f"{audio_id}.mp3"
        path.write_bytes(mp3_bytes)
        return audio_id

    def load(self, audio_id: str) -> bytes | None:
        """Load MP3 bytes by id; return None if not found."""
        path = self.base_dir / f"{audio_id}.mp3"
        if not path.exists():
            return None
        return path.read_bytes()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_audio_storage.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add execution/audio_storage.py tests/test_audio_storage.py
git commit -m "feat: audio storage with uuid keys for Twilio playback"
```

---

## Task 6: Modal App Skeleton + Audio Endpoint

**Files:**
- Create: `modal_app.py`
- Test: `tests/test_modal_app.py`

We'll build the Modal app FastAPI in three sub-tasks:
- Task 6: skeleton + `/audio/{audio_id}` endpoint
- Task 7: `/voice/incoming` endpoint
- Task 8: `/voice/gather` endpoint

- [ ] **Step 1: Write the failing test**

`tests/test_modal_app.py`:

```python
from unittest.mock import patch
from fastapi.testclient import TestClient

from modal_app import api, get_storage


def test_audio_endpoint_returns_mp3_bytes(tmp_path, monkeypatch):
    # Override the storage dependency to point to tmp_path
    from execution.audio_storage import AudioStorage
    storage = AudioStorage(base_dir=tmp_path)
    audio_id = storage.save(b"\xff\xfb\x90fake_mp3")

    api.dependency_overrides[get_storage] = lambda: storage
    try:
        client = TestClient(api)
        response = client.get(f"/audio/{audio_id}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"
        assert response.content == b"\xff\xfb\x90fake_mp3"
    finally:
        api.dependency_overrides.clear()


def test_audio_endpoint_404_when_missing(tmp_path):
    from execution.audio_storage import AudioStorage
    storage = AudioStorage(base_dir=tmp_path)

    api.dependency_overrides[get_storage] = lambda: storage
    try:
        client = TestClient(api)
        response = client.get("/audio/nonexistent")
        assert response.status_code == 404
    finally:
        api.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_modal_app.py -v
```

Expected: FAILS with `ImportError` (no `modal_app` yet).

- [ ] **Step 3: Write minimal implementation**

`modal_app.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_modal_app.py::test_audio_endpoint_returns_mp3_bytes tests/test_modal_app.py::test_audio_endpoint_404_when_missing -v
```

Expected: Both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add modal_app.py tests/test_modal_app.py
git commit -m "feat: Modal+FastAPI skeleton with /audio/{id} endpoint"
```

---

## Task 7: Twilio `/voice/incoming` Endpoint

When a caller dials our number, Twilio POSTs to `/voice/incoming`. We respond with TwiML that:
1. Plays a greeting (generated via ElevenLabs).
2. Uses `<Gather input="speech">` to capture the caller's speech and POST it to `/voice/gather`.

We keep conversation history in-memory keyed by `CallSid` (Twilio's per-call ID). For Phase 1 a Python dict is fine; later phases move this to Supabase.

**Files:**
- Modify: `modal_app.py`
- Modify: `tests/test_modal_app.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_modal_app.py`:

```python
from unittest.mock import MagicMock


def test_voice_incoming_returns_twiml_with_play_and_gather(tmp_path, monkeypatch):
    from execution.audio_storage import AudioStorage
    storage = AudioStorage(base_dir=tmp_path)

    api.dependency_overrides[get_storage] = lambda: storage

    # Mock TTS so we don't hit ElevenLabs in tests
    import modal_app
    monkeypatch.setattr(modal_app, "synthesize_speech", lambda text: b"fake_mp3_greeting")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://test.modal.run")

    try:
        client = TestClient(api)
        response = client.post(
            "/voice/incoming",
            data={"CallSid": "CAtest123", "From": "+15555550111"},
        )
        assert response.status_code == 200
        assert "application/xml" in response.headers["content-type"]
        body = response.text

        # TwiML structure
        assert "<Response>" in body
        assert "<Play>" in body
        assert "<Gather" in body
        assert 'input="speech"' in body
        assert 'action="/voice/gather"' in body
        # Audio URL points at our /audio/{id} endpoint
        assert "https://test.modal.run/audio/" in body
    finally:
        api.dependency_overrides.clear()


def test_voice_incoming_initializes_conversation_history(tmp_path, monkeypatch):
    from execution.audio_storage import AudioStorage
    storage = AudioStorage(base_dir=tmp_path)
    api.dependency_overrides[get_storage] = lambda: storage

    import modal_app
    monkeypatch.setattr(modal_app, "synthesize_speech", lambda text: b"x")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://test.modal.run")
    modal_app.CONVERSATIONS.clear()

    try:
        client = TestClient(api)
        client.post(
            "/voice/incoming",
            data={"CallSid": "CAabc", "From": "+15555550111"},
        )
        assert "CAabc" in modal_app.CONVERSATIONS
        # Greeting recorded as the first assistant message
        assert modal_app.CONVERSATIONS["CAabc"][-1]["role"] == "assistant"
    finally:
        api.dependency_overrides.clear()
        modal_app.CONVERSATIONS.clear()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_modal_app.py -v
```

Expected: New tests FAIL with `AttributeError` or 404.

- [ ] **Step 3: Modify `modal_app.py` — add imports, conversation store, and endpoint**

Add to top of file (after the existing imports):

```python
from fastapi import Form
from fastapi.responses import Response as FastAPIResponse

from execution.business_config import get_business_config, build_system_prompt
from execution.claude_conversation import generate_reply
from execution.elevenlabs_tts import synthesize_speech

# In-memory conversation store keyed by Twilio CallSid.
# Phase 5 replaces this with Supabase. Fine for single-process Phase 1 MVP.
CONVERSATIONS: dict[str, list[dict]] = {}

GREETING_TEMPLATE = "Thank you for calling {name}. How can I help you today?"
```

Add this endpoint to `modal_app.py` (after the `/audio/{audio_id}` endpoint):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_modal_app.py -v
```

Expected: All tests PASS (including the two new ones).

- [ ] **Step 5: Commit**

```bash
git add modal_app.py tests/test_modal_app.py
git commit -m "feat: /voice/incoming returns TwiML with greeting + gather"
```

---

## Task 8: Twilio `/voice/gather` Endpoint

After `<Gather>` captures speech, Twilio POSTs the transcript to `/voice/gather` as `SpeechResult`. We:
1. Append the user's text to the conversation history.
2. Call Claude for a reply.
3. Append Claude's reply to history.
4. Synthesize the reply via ElevenLabs.
5. Return TwiML: `<Play>` the reply + another `<Gather>` to listen for the next turn.

**Files:**
- Modify: `modal_app.py`
- Modify: `tests/test_modal_app.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_modal_app.py`:

```python
def test_voice_gather_processes_speech_and_returns_twiml(tmp_path, monkeypatch):
    from execution.audio_storage import AudioStorage
    storage = AudioStorage(base_dir=tmp_path)
    api.dependency_overrides[get_storage] = lambda: storage

    import modal_app
    monkeypatch.setattr(modal_app, "synthesize_speech", lambda text: b"fake_audio")
    monkeypatch.setattr(
        modal_app, "generate_reply",
        lambda system_prompt, history, new_message: "Sure, what day works?",
    )
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://test.modal.run")
    modal_app.CONVERSATIONS["CA999"] = [{"role": "assistant", "content": "Hi!"}]

    try:
        client = TestClient(api)
        response = client.post(
            "/voice/gather",
            data={"CallSid": "CA999", "SpeechResult": "I want an appointment"},
        )
        assert response.status_code == 200
        body = response.text
        assert "<Play>" in body
        assert "<Gather" in body
        assert 'action="/voice/gather"' in body
    finally:
        api.dependency_overrides.clear()
        modal_app.CONVERSATIONS.clear()


def test_voice_gather_appends_user_and_assistant_to_history(tmp_path, monkeypatch):
    from execution.audio_storage import AudioStorage
    storage = AudioStorage(base_dir=tmp_path)
    api.dependency_overrides[get_storage] = lambda: storage

    import modal_app
    monkeypatch.setattr(modal_app, "synthesize_speech", lambda text: b"x")
    monkeypatch.setattr(
        modal_app, "generate_reply",
        lambda system_prompt, history, new_message: "Of course.",
    )
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://test.modal.run")
    modal_app.CONVERSATIONS["CA111"] = [{"role": "assistant", "content": "Hi!"}]

    try:
        client = TestClient(api)
        client.post(
            "/voice/gather",
            data={"CallSid": "CA111", "SpeechResult": "Book me an appointment"},
        )
        history = modal_app.CONVERSATIONS["CA111"]
        # Started with 1 message, added user + assistant = 3 total
        assert len(history) == 3
        assert history[1] == {"role": "user", "content": "Book me an appointment"}
        assert history[2] == {"role": "assistant", "content": "Of course."}
    finally:
        api.dependency_overrides.clear()
        modal_app.CONVERSATIONS.clear()


def test_voice_gather_handles_missing_speech_result(tmp_path, monkeypatch):
    from execution.audio_storage import AudioStorage
    storage = AudioStorage(base_dir=tmp_path)
    api.dependency_overrides[get_storage] = lambda: storage

    import modal_app
    monkeypatch.setattr(modal_app, "synthesize_speech", lambda text: b"x")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://test.modal.run")

    try:
        client = TestClient(api)
        # No SpeechResult sent — Twilio sends empty when nothing captured
        response = client.post("/voice/gather", data={"CallSid": "CA222", "SpeechResult": ""})
        assert response.status_code == 200
        # Should re-prompt (gather again), not crash
        assert "<Gather" in response.text
    finally:
        api.dependency_overrides.clear()
        modal_app.CONVERSATIONS.clear()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_modal_app.py -v
```

Expected: New tests FAIL (404 on `/voice/gather`).

- [ ] **Step 3: Add `/voice/gather` to `modal_app.py`**

Append after `voice_incoming`:

```python
REPROMPT_TEXT = "I didn't catch that. Could you say it again?"


@api.post("/voice/gather")
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_modal_app.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: All tests across all files PASS.

- [ ] **Step 6: Commit**

```bash
git add modal_app.py tests/test_modal_app.py
git commit -m "feat: /voice/gather processes speech, calls Claude, replies with TTS"
```

---

## Task 9: Modal Secrets + Deployment

**Files:** None modified — Modal CLI commands only.

- [ ] **Step 1: Create Modal secret**

```bash
modal secret create ai-receptionist-secrets \
  ANTHROPIC_API_KEY=sk-ant-xxx \
  ELEVENLABS_API_KEY=xxx \
  ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM \
  TWILIO_ACCOUNT_SID=ACxxx \
  TWILIO_AUTH_TOKEN=xxx \
  TWILIO_PHONE_NUMBER=+15555550000 \
  PUBLIC_BASE_URL=https://placeholder
```

(Replace `xxx` with real values from your existing Twilio / ElevenLabs / Anthropic accounts.)

Expected: `Created secret 'ai-receptionist-secrets'.`

- [ ] **Step 2: Deploy to Modal**

```bash
modal deploy modal_app.py
```

Expected output: A deployment URL like `https://your-username--ai-receptionist-phone-fastapi-app.modal.run`. **Copy this URL.**

- [ ] **Step 3: Update `PUBLIC_BASE_URL` secret with the actual Modal URL**

```bash
modal secret create ai-receptionist-secrets \
  ANTHROPIC_API_KEY=sk-ant-xxx \
  ELEVENLABS_API_KEY=xxx \
  ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM \
  TWILIO_ACCOUNT_SID=ACxxx \
  TWILIO_AUTH_TOKEN=xxx \
  TWILIO_PHONE_NUMBER=+15555550000 \
  PUBLIC_BASE_URL=https://your-username--ai-receptionist-phone-fastapi-app.modal.run \
  --force
```

Then redeploy:

```bash
modal deploy modal_app.py
```

- [ ] **Step 4: Smoke-test the audio endpoint**

```bash
curl -i https://your-username--ai-receptionist-phone-fastapi-app.modal.run/audio/test
```

Expected: HTTP 404 (no such audio yet — but the endpoint responded, proving the app is alive).

---

## Task 10: Wire Twilio Phone Number to Modal

**Files:** None — Twilio Console only.

- [ ] **Step 1: Open the Twilio Console**

Go to https://console.twilio.com/ → Phone Numbers → Manage → Active Numbers → click your number.

- [ ] **Step 2: Set the Voice webhook**

Under "Voice Configuration":
- "A call comes in": **Webhook**
- URL: `https://your-username--ai-receptionist-phone-fastapi-app.modal.run/voice/incoming`
- HTTP method: **POST**

Click **Save configuration**.

- [ ] **Step 3: Make a real test call**

Dial your Twilio number from a phone.

Expected:
1. The greeting plays in the ElevenLabs voice ("Thank you for calling Bright Smile Dental...").
2. After it finishes, you can speak ("What are your hours?").
3. The AI replies in voice with relevant info from the system prompt.
4. The conversation continues for multiple turns.

If anything fails, check:
```bash
modal app logs ai-receptionist-phone
```

- [ ] **Step 4: Commit deployment notes**

Add `docs/deployment.md` with the Modal URL and Twilio configuration steps:

```markdown
# Deployment Notes — Phase 1

**Modal app:** `ai-receptionist-phone`
**URL:** https://your-username--ai-receptionist-phone-fastapi-app.modal.run
**Twilio number:** +15555550000
**Webhook:** /voice/incoming (POST)

## Redeploy
\`\`\`
modal deploy modal_app.py
\`\`\`

## Logs
\`\`\`
modal app logs ai-receptionist-phone
\`\`\`
```

```bash
git add docs/deployment.md
git commit -m "docs: deployment notes for Phase 1"
git push origin main
```

---

## Done Criteria for Phase 1

- ✅ All pytest tests pass (`pytest -v`)
- ✅ `modal_app.py` deploys without errors
- ✅ Calling the Twilio number triggers the greeting in ElevenLabs voice
- ✅ Multi-turn conversation works (Claude tracks context per `CallSid`)
- ✅ All commits pushed to `origin/main`

## Out of Scope (Later Phases)

| Phase | What it adds |
|---|---|
| 2 | Chat widget (same brain) |
| 3 | Google Calendar booking via tool calling |
| 4 | Human transfer + SMS/email follow-ups |
| 5 | Multi-tenant: Supabase, lookup business by Twilio number |
| 6 | Next.js dashboard + onboarding |
| 7 | Stripe billing + agency model |

## Known Limitations

- **Latency:** Twilio `<Gather>` STT + sequential Claude → ElevenLabs → Modal Volume → Twilio fetch is ~2–3s per turn. The 1.5s spec target requires Twilio Media Streams + bidirectional audio streaming — refactor in Phase 8 once core flows are validated.
- **Single business:** Hardcoded in `business_config.py`. Multi-tenant lookup added in Phase 5.
- **No transcript persistence:** `CONVERSATIONS` is in-memory only. Lost on container restart. Phase 5 moves it to Supabase.
- **No call recording or summaries:** Added later.

## End of Plan
