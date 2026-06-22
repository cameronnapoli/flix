#!/usr/bin/env python3
"""
Align a TTML's subtitle timing to a video's actual audio, then embed as SRT.

STT-transcribe a short sample, ask Claude for the constant offset between
subtitle and audio time, shift all cues, write .srt, mux into the .mp4.
"""

import argparse
import re
import statistics
import sys
from pathlib import Path

from lib.cli import select_file
from lib.constants import DATA, TTML_EXTS, VIDEO_EXTS
from lib.ffmpeg import fmt_time, run
from lib.llm import complete_structured
from lib.stt import Word, transcribe
from lib.ttml import Cue, get_language, parse_ttml, write_srt

SAMPLE_SECONDS = 45
WORDS_PER_TIMESTAMP = 8  # anchor every N words instead of every word, to save tokens

SAMPLE_BUFFER = 20  # slack around a skipped-ahead sample, to absorb the unknown offset
MIN_DIALOGUE_SECONDS = 10  # below this, skip ahead past the cold open

MATCH_SEQ_LEN = 3  # consecutive words needed for a deterministic match
MIN_DETERMINISTIC_MATCHES = 4  # below this, fall back to the LLM
MAX_DETERMINISTIC_SPREAD = 2.5  # seconds; wider spread than this isn't trustworthy
VERIFY_TOLERANCE = 1.5  # seconds
MIN_VERIFY_FRAC = 0.5  # fraction of matches that must agree with the chosen offset

SYSTEM_PROMPT = """Given a speech-to-text transcript (audio timestamps) and TTML \
subtitle cues (possibly offset, e.g. from trimming) covering the same speech, find \
the constant offset in seconds to ADD to subtitle timestamps so they match the audio.

Match several cues to their corresponding transcript words by content, not just by \
position, since the dub wording can differ from the subtitle wording for the same line. \
Ignore cues that are purely bracketed sound effects or stage directions (e.g. "[suspira]", \
"[graznido de gaviotas]") since they have no corresponding transcript words. Compute the \
offset (audio_time - subtitle_time) for each matched pair, and return the median -- double \
check the sign of your final answer against at least two matched pairs before responding."""

OFFSET_SCHEMA = {
    "type": "object",
    "properties": {"offset_seconds": {"type": "number"}},
    "required": ["offset_seconds"],
}


def parse_args():
    parser = argparse.ArgumentParser(description="Align a TTML's subtitle timing to a video's audio and embed it.")
    parser.add_argument("-f", "--file", help="input video file (skip interactive selection)")
    parser.add_argument("-t", "--ttml", help="input TTML file (skip interactive selection)")
    parser.add_argument(
        "--offset", type=float,
        help="skip AI offset detection and use this constant offset (seconds, added to subtitle timestamps)",
    )
    return parser.parse_args()


def extract_sample_audio(video: Path, start: float, seconds: float, out: Path) -> None:
    args = ["ffmpeg"]
    if start > 0:
        args += ["-ss", str(start)]
    args += ["-i", str(video), "-t", str(seconds), "-vn", "-ac", "1", "-ar", "16000", "-y", str(out)]
    run(args, f"Extract {seconds:.0f}s of audio for alignment (from {fmt_time(start)})")


def is_dialogue(text: str) -> bool:
    """False for bracketed stage directions or sung (♪) lines -- unreliable to match against speech."""
    if "♪" in text:
        return False
    return bool(re.sub(r"\[[^\]]*\]", "", text).strip())


def find_sample_start(cues: list[Cue]) -> float:
    """Skip ahead past a cold open (song/sound effects) if the default window lacks real dialogue."""
    dialogue_in_window = sum(
        c.end - c.start for c in cues if c.start < SAMPLE_SECONDS and is_dialogue(c.text)
    )
    if dialogue_in_window >= MIN_DIALOGUE_SECONDS:
        return 0.0
    for c in cues:
        if is_dialogue(c.text):
            return max(0.0, c.start - 2.0)
    return 0.0


def _compact_transcript(words: list[Word]) -> str:
    """Render words as text with a timestamp anchor every N words, not every word."""
    chunks = []
    for i in range(0, len(words), WORDS_PER_TIMESTAMP):
        group = words[i : i + WORDS_PER_TIMESTAMP]
        chunks.append(f"[{group[0].start:.2f}] " + " ".join(w.text for w in group))
    return "\n".join(chunks)


def _normalize_word(w: str) -> str:
    return re.sub(r"[^\w]", "", w.lower())


def _content_words(text: str) -> list[str]:
    """Normalized words from a cue, with bracketed stage directions stripped."""
    cleaned = re.sub(r"\[[^\]]*\]", "", text)
    return [_normalize_word(w) for w in re.findall(r"[^\W\d_]+", cleaned, re.UNICODE)]


def deterministic_offsets(words: list[Word], cues: list[Cue], window_start: float, window_end: float) -> list[float]:
    """Offsets from cues whose first few words match the transcript verbatim and unambiguously."""
    norm = [_normalize_word(w.text) for w in words]
    offsets = []
    for c in cues:
        if not (window_start <= c.start < window_end) or not is_dialogue(c.text):
            continue
        target = _content_words(c.text)[:MATCH_SEQ_LEN]
        if len(target) < MATCH_SEQ_LEN:
            continue
        matches = [i for i in range(len(norm) - MATCH_SEQ_LEN + 1) if norm[i : i + MATCH_SEQ_LEN] == target]
        if len(matches) == 1:
            offsets.append(words[matches[0]].start - c.start)
    return offsets


def ask_llm_for_offset(words: list[Word], cues: list[Cue], window_start: float, window_end: float) -> float:
    transcript = _compact_transcript(words)
    window = [c for c in cues if window_start <= c.start < window_end]
    subtitles = "\n".join(f"[{c.start:.2f}] {c.text}" for c in window)
    prompt = f"AUDIO TRANSCRIPT (word timestamps):\n{transcript}\n\nSUBTITLE CUES:\n{subtitles}"
    result = complete_structured(prompt, OFFSET_SCHEMA, system=SYSTEM_PROMPT)
    return float(result["offset_seconds"])


def compute_offset(words: list[Word], cues: list[Cue], window_start: float, window_end: float) -> tuple[float, str]:
    """Prefer exact word matching; fall back to the LLM if too few lines match verbatim."""
    det = deterministic_offsets(words, cues, window_start, window_end)
    if len(det) >= MIN_DETERMINISTIC_MATCHES and max(det) - min(det) <= MAX_DETERMINISTIC_SPREAD:
        return statistics.median(det), f"deterministic ({len(det)} exact word matches)"
    offset = ask_llm_for_offset(words, cues, window_start, window_end)
    return offset, "AI-estimated"


def verify_offset(words: list[Word], cues: list[Cue], offset: float, window_start: float, window_end: float) -> float:
    """Fraction of deterministic matches that agree with `offset` -- catches a wrong/hallucinated AI answer."""
    det = deterministic_offsets(words, cues, window_start, window_end)
    if not det:
        return 1.0  # nothing to check against
    agreeing = sum(1 for d in det if abs(d - offset) <= VERIFY_TOLERANCE)
    return agreeing / len(det)


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

    if args.offset is not None:
        offset = args.offset
        print(f"Using manual offset: {offset:+.3f}s")
    else:
        sample_start = find_sample_start(cues)
        if sample_start > 0:
            print(f"Default sample window looks like a cold open (song/sound effects) -- "
                  f"sampling from {fmt_time(sample_start)} instead")
            audio_start = max(0.0, sample_start - SAMPLE_BUFFER)
            audio_seconds = SAMPLE_SECONDS + 2 * SAMPLE_BUFFER
        else:
            audio_start = 0.0
            audio_seconds = SAMPLE_SECONDS
        window_start, window_end = audio_start, audio_start + audio_seconds

        sample_audio = out_dir / f"{video.stem}_sample.wav"
        extract_sample_audio(video, audio_start, audio_seconds, sample_audio)

        print("Transcribing sample audio via ElevenLabs...")
        words = transcribe(sample_audio)
        sample_audio.unlink()
        for w in words:
            w.start += audio_start
            w.end += audio_start

        transcript_path = out_dir / f"{video.stem}_transcript.txt"
        transcript_path.write_text(_compact_transcript(words), encoding="utf-8")
        print(f"Wrote {transcript_path}")

        print("Computing the subtitle/audio offset...")
        offset, method = compute_offset(words, cues, window_start, window_end)
        print(f"Offset: {offset:+.3f}s ({method})")

        match_frac = verify_offset(words, cues, offset, window_start, window_end)
        if match_frac < MIN_VERIFY_FRAC:
            sys.exit(
                f"Offset {offset:+.3f}s failed the sanity check -- only {match_frac:.0%} of exact word "
                f"matches agree with it (need >={MIN_VERIFY_FRAC:.0%}). This usually means the AI's "
                f"answer is wrong/hallucinated. Re-run, or pass --offset to set it manually."
            )
        print(f"Offset sanity check passed ({match_frac:.0%} of exact word matches agree)")

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
