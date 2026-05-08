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
