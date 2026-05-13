from fastapi.testclient import TestClient

from modal_app import api, get_storage, validate_twilio


def _bypass_twilio_validation() -> None:
    """Helper for tests: install a no-op override for the Twilio validator."""
    api.dependency_overrides[validate_twilio] = lambda: None


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


def test_voice_incoming_returns_twiml_with_play_and_gather(tmp_path, monkeypatch):
    from execution.audio_storage import AudioStorage
    storage = AudioStorage(base_dir=tmp_path)

    api.dependency_overrides[get_storage] = lambda: storage
    _bypass_twilio_validation()

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
    _bypass_twilio_validation()

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


def test_voice_gather_processes_speech_and_returns_twiml(tmp_path, monkeypatch):
    from execution.audio_storage import AudioStorage
    storage = AudioStorage(base_dir=tmp_path)
    api.dependency_overrides[get_storage] = lambda: storage
    _bypass_twilio_validation()

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
    _bypass_twilio_validation()

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
    _bypass_twilio_validation()

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


def test_voice_incoming_rejects_unsigned_request(tmp_path, monkeypatch):
    """A POST without a valid X-Twilio-Signature must return 403."""
    from execution.audio_storage import AudioStorage
    storage = AudioStorage(base_dir=tmp_path)
    api.dependency_overrides[get_storage] = lambda: storage
    # Note: NOT bypassing validate_twilio — we want it to run.

    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "fake-auth-token")
    monkeypatch.delenv("TWILIO_SKIP_VALIDATION", raising=False)

    try:
        client = TestClient(api)
        response = client.post(
            "/voice/incoming",
            data={"CallSid": "CAbad", "From": "+15555550111"},
            # No X-Twilio-Signature header
        )
        assert response.status_code == 403
    finally:
        api.dependency_overrides.clear()


def test_voice_incoming_skip_validation_env_var(tmp_path, monkeypatch):
    """TWILIO_SKIP_VALIDATION=true bypasses the signature check (dev only)."""
    from execution.audio_storage import AudioStorage
    storage = AudioStorage(base_dir=tmp_path)
    api.dependency_overrides[get_storage] = lambda: storage

    import modal_app
    monkeypatch.setattr(modal_app, "synthesize_speech", lambda text: b"x")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://test.modal.run")
    monkeypatch.setenv("TWILIO_SKIP_VALIDATION", "true")

    try:
        client = TestClient(api)
        response = client.post(
            "/voice/incoming",
            data={"CallSid": "CAskip", "From": "+15555550111"},
        )
        assert response.status_code == 200
    finally:
        api.dependency_overrides.clear()
