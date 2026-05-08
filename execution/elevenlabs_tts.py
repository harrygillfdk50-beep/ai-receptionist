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
