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


def probe_keyframe_interval(path: Path, around: float = 0.0, window: float = 120.0) -> float:
    """Estimate the keyframe (GOP) interval near `around`, in seconds."""
    default = 10.0
    offset = max(0.0, around - 5.0)
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-read_intervals", f"{offset}%+{window}",
            "-show_entries", "packet=pts_time,flags",
            "-of", "csv=p=0",
            str(path),
        ],
        capture_output=True, text=True,
    )
    times = []
    for line in result.stdout.splitlines():
        pts_time, _, flags = line.partition(",")
        if "K" not in flags:
            continue
        try:
            times.append(float(pts_time))
        except ValueError:
            continue
    times.sort()
    gaps = [b - a for a, b in zip(times, times[1:])]
    return max(gaps) if gaps else default


def cut_segment(src: Path, start: float, end: float | None, out: Path) -> None:
    """
    Extract [start, end) from src into out using stream copy (fast, keyframe-aligned,
    not frame-accurate). Seeks a bit before `start` since the keyframe seek can
    otherwise land after it and chop off the beginning of the segment.
    """
    interval = probe_keyframe_interval(src, around=start)
    buffered_start = max(0.0, start - interval - 1.0)
    args = ["ffmpeg", "-ss", str(buffered_start)]
    if end is not None:
        # -to (input option) is an absolute source timestamp, so it's unaffected
        # by where the -ss seek actually lands -- unlike -t, a relative duration.
        args += ["-to", str(end)]
    args += ["-i", str(src), "-c", "copy", "-y", str(out)]
    desc = f"Cut {fmt_time(start)} -> {fmt_time(end) if end is not None else 'end'} (seek buffer {fmt_time(buffered_start)})"
    run(args, desc)
