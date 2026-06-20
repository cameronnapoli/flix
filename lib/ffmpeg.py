"""Generic ffmpeg/ffprobe helpers shared by the flix pipeline scripts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run(args: list[str], desc: str) -> None:
    """Run an ffmpeg/ffprobe command, printing it and exiting loudly on failure."""
    print(f"\n[ffmpeg] {desc}")
    print("  " + " ".join(str(a) for a in args))
    result = subprocess.run(args, text=True, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(result.stderr[-3000:])
        sys.exit(f"ffmpeg failed (exit {result.returncode})")


def probe_duration(path: Path) -> float:
    """Return the duration of a media file in seconds, via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True, text=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def parse_time(s: str) -> float:
    """Parse HH:MM:SS, MM:SS, or bare seconds into float seconds."""
    parts = [float(p) for p in s.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0]


def fmt_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def cut_segment(src: Path, start: float, end: float | None, out: Path) -> None:
    """
    Extract [start, end) from src into out using stream copy (fast, keyframe-aligned).
    Not frame-accurate -- intended for rough cuts, not precise edits.
    """
    args = ["ffmpeg", "-ss", str(start), "-i", str(src)]
    if end is not None:
        args += ["-t", str(end - start)]
    args += ["-c", "copy", "-y", str(out)]
    desc = f"Cut {fmt_time(start)} -> {fmt_time(end) if end is not None else 'end'}"
    run(args, desc)
