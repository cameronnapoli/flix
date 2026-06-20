"""ElevenLabs speech-to-text helper -- transcribes audio with word-level timestamps."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

_client: ElevenLabs | None = None


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
    return [
        Word(text=w.text, start=w.start, end=w.end)
        for w in result.words
        if w.type == "word"
    ]
