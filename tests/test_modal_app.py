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
