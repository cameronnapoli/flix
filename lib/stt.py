"""ElevenLabs speech-to-text helper -- transcribes audio with word-level timestamps."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

_client: ElevenLabs | None = None

# Scribe v1 pay-as-you-go rate: https://elevenlabs.io/pricing/api
_SCRIBE_COST_PER_HOUR = 0.22


@dataclass
class Word:
    text: str
    start: float
    end: float


def _get_client() -> ElevenLabs:
    global _client
    if _client is None:
        _client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    return _client


def estimate_cost(audio_duration_secs: float) -> float:
    """Estimate USD cost for transcribing audio of the given duration."""
    return audio_duration_secs / 3600 * _SCRIBE_COST_PER_HOUR


def transcribe(path: Path) -> list[Word]:
    """Transcribe an audio/video file, returning word-level timestamps."""
    with open(path, "rb") as f:
        result = _get_client().speech_to_text.convert(
            file=f,
            model_id="scribe_v1",
            timestamps_granularity="word",
            tag_audio_events=False,
            diarize=False,
        )
    if result.audio_duration_secs is not None:
        cost = estimate_cost(result.audio_duration_secs)
        print(f"stt: {result.audio_duration_secs:.1f}s audio, est. cost ${cost:.4f}")

    return [
        Word(text=w.text, start=w.start, end=w.end)
        for w in result.words
        if w.type == "word"
    ]
