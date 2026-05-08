from unittest.mock import MagicMock, patch
from execution.elevenlabs_tts import synthesize_speech


@patch("execution.elevenlabs_tts.ElevenLabs")
def test_synthesize_speech_returns_bytes(mock_eleven_cls, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    mock_client = MagicMock()
    mock_eleven_cls.return_value = mock_client
    mock_client.text_to_speech.convert.return_value = iter([b"fake_mp3_chunk_1", b"fake_mp3_chunk_2"])

    audio = synthesize_speech("Hello there!")

    assert isinstance(audio, bytes)
    assert audio == b"fake_mp3_chunk_1fake_mp3_chunk_2"


@patch("execution.elevenlabs_tts.ElevenLabs")
def test_synthesize_speech_uses_configured_voice_id(mock_eleven_cls, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test_voice_xyz")
    mock_client = MagicMock()
    mock_eleven_cls.return_value = mock_client
    mock_client.text_to_speech.convert.return_value = iter([b"x"])

    synthesize_speech("Hello")

    call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
    assert call_kwargs["voice_id"] == "test_voice_xyz"


@patch("execution.elevenlabs_tts.ElevenLabs")
def test_synthesize_speech_requests_mp3_format(mock_eleven_cls, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    mock_client = MagicMock()
    mock_eleven_cls.return_value = mock_client
    mock_client.text_to_speech.convert.return_value = iter([b"x"])

    synthesize_speech("Hello")

    call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
    assert "mp3" in call_kwargs["output_format"]
