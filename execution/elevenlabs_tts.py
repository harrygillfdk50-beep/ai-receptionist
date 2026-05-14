"""ElevenLabs text-to-speech wrapper.

Returns MP3 bytes. Twilio's <Play> verb supports MP3 over HTTPS, so we serve
these bytes from `modal_app.py`'s /audio/{id} endpoint.
"""

import os
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs "Rachel"
DEFAULT_MODEL = "eleven_turbo_v2_5"  # low-latency, good for phone
# 44.1 kHz mono at 128 kbps — much cleaner than the original 32 kbps we shipped.
# Twilio downsamples to 8 kHz mu-law for the phone leg, but starting from a
# high-bitrate source dramatically reduces muffled / compression artifacts.
# Note: ElevenLabs has a fixed allowlist of formats — mp3_22050_128 doesn't
# exist; the valid 22 kHz option is mp3_22050_32 (too compressed) so we use
# mp3_44100_128 instead.
OUTPUT_FORMAT = "mp3_44100_128"

# Default voice tuning for a phone receptionist:
# - stability 0.5: balanced (lower = more expressive, higher = more monotone)
# - similarity_boost 0.75: stay close to the chosen voice's character
# - style 0.0: don't push extra "performance" — sounds more natural on phone
# - speed 1.1: a touch faster than default; default 1.0 feels sluggish on calls
DEFAULT_VOICE_SETTINGS = VoiceSettings(
    stability=0.5,
    similarity_boost=0.75,
    style=0.0,
    use_speaker_boost=True,
    speed=1.1,
)


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
        voice_settings=DEFAULT_VOICE_SETTINGS,
    )

    return b"".join(audio_stream)
