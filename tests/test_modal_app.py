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
