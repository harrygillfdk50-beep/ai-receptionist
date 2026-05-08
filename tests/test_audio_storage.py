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
