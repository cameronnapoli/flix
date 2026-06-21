#!/usr/bin/env python3
"""
Align a TTML's subtitle timing to a video's actual audio, then embed as SRT.

STT-transcribe a short sample, ask Claude for the constant offset between
subtitle and audio time, shift all cues, write .srt, mux into the .mp4.
"""

import argparse
from pathlib import Path

from lib.cli import select_file
from lib.constants import DATA, TTML_EXTS, VIDEO_EXTS
from lib.ffmpeg import run
from lib.llm import complete_structured
from lib.stt import Word, transcribe
from lib.ttml import Cue, get_language, parse_ttml, write_srt

SAMPLE_SECONDS = 45
WORDS_PER_TIMESTAMP = 8  # anchor every N words instead of every word, to save tokens

SYSTEM_PROMPT = """Given a speech-to-text transcript (audio timestamps) and TTML \
subtitle cues (possibly offset, e.g. from trimming) covering the same speech, find \
the constant offset in seconds to ADD to subtitle timestamps so they match the audio."""

OFFSET_SCHEMA = {
    "type": "object",
    "properties": {"offset_seconds": {"type": "number"}},
    "required": ["offset_seconds"],
}


def parse_args():
    parser = argparse.ArgumentParser(description="Align a TTML's subtitle timing to a video's audio and embed it.")
    parser.add_argument("-f", "--file", help="input video file (skip interactive selection)")
    parser.add_argument("-t", "--ttml", help="input TTML file (skip interactive selection)")
    return parser.parse_args()


def extract_sample_audio(video: Path, seconds: int, out: Path) -> None:
    run(
        ["ffmpeg", "-i", str(video), "-t", str(seconds), "-vn", "-ac", "1", "-ar", "16000", "-y", str(out)],
        f"Extract first {seconds}s of audio for alignment",
    )


def _compact_transcript(words: list[Word]) -> str:
    """Render words as text with a timestamp anchor every N words, not every word."""
    chunks = []
    for i in range(0, len(words), WORDS_PER_TIMESTAMP):
        group = words[i : i + WORDS_PER_TIMESTAMP]
        chunks.append(f"[{group[0].start:.2f}] " + " ".join(w.text for w in group))
    return "\n".join(chunks)


def compute_offset(words: list[Word], cues: list[Cue]) -> float:
    transcript = _compact_transcript(words)
    window = [c for c in cues if c.start < SAMPLE_SECONDS]
    subtitles = "\n".join(f"[{c.start:.2f}] {c.text}" for c in window)
    prompt = f"AUDIO TRANSCRIPT (word timestamps):\n{transcript}\n\nSUBTITLE CUES:\n{subtitles}"
    result = complete_structured(prompt, OFFSET_SCHEMA, system=SYSTEM_PROMPT)
    return float(result["offset_seconds"])


def embed_subtitles(video: Path, srt: Path, lang: str, out: Path) -> None:
    run(
        [
            "ffmpeg", "-i", str(video), "-i", str(srt),
            "-map", "0:v", "-map", "0:a", "-map", "1",
            "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text",
            "-map_metadata", "-1",
            "-metadata:s:v:0", "handler_name=VideoHandler",
            "-metadata:s:a:0", "handler_name=SoundHandler",
            "-metadata:s:v:0", "encoder=",
            "-metadata:s:s:0", "handler_name=SubtitleHandler",
            "-metadata:s:s:0", f"language={lang}",
            "-disposition:s:0", "default",
            "-y", str(out),
        ],
        "Mux video + subtitles, strip stale metadata",
    )


def main():
    print("Merge -- align TTML subtitles to audio and embed as SRT")
    args = parse_args()

    video = select_file(args.file, DATA, VIDEO_EXTS, "video")
    ttml = select_file(args.ttml, DATA, TTML_EXTS, "TTML")

    out_dir = DATA / "merged"
    out_dir.mkdir(exist_ok=True)

    cues = parse_ttml(ttml)
    print(f"Parsed {len(cues)} subtitle cues")

    sample_audio = out_dir / f"{video.stem}_sample.wav"
    extract_sample_audio(video, SAMPLE_SECONDS, sample_audio)

    print("Transcribing sample audio via ElevenLabs...")
    words = transcribe(sample_audio)
    sample_audio.unlink()

    transcript_path = out_dir / f"{video.stem}_transcript.txt"
    transcript_path.write_text(_compact_transcript(words), encoding="utf-8")
    print(f"Wrote {transcript_path}")

    print("Asking Claude for the subtitle/audio offset...")
    offset = compute_offset(words, cues)
    print(f"Offset: {offset:+.3f}s")

    for cue in cues:
        cue.start += offset
        cue.end += offset

    srt_path = out_dir / f"{ttml.stem}.srt"
    write_srt(cues, srt_path)
    print(f"Wrote {srt_path}")

    lang = get_language(ttml)
    out_video = out_dir / f"{video.stem}.mp4"
    embed_subtitles(video, srt_path, lang, out_video)
    print(f"\nDone. -> {out_video}")


if __name__ == "__main__":
    main()
