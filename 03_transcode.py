#!/usr/bin/env python3
"""
Compress and reencode a video to the standard delivery format.

Scales to 720p and reencodes with H.264 (CRF 23, preset slow) + AAC audio,
copying subtitle streams through untouched.
"""

import sys
from pathlib import Path

from lib.ffmpeg import run

DATA = Path("data")
VIDEO_EXTS = (".mov", ".mp4", ".mkv")
SEARCH_DIRS = (DATA / "merged", DATA)


def confirm(msg: str) -> bool:
    return input(f"{msg} (y/n): ").strip().lower() == "y"


def select_input_file() -> Path:
    for d in SEARCH_DIRS:
        if not d.exists():
            continue
        matches = sorted(p for p in d.iterdir() if p.suffix.lower() in VIDEO_EXTS)
        if matches:
            video = matches[0]
            print(f"Found video: {video}  ({video.stat().st_size / 1e9:.2f} GB)")
            if not confirm("Use this file?"):
                sys.exit("Aborted.")
            return video
    searched = ", ".join(str(d) for d in SEARCH_DIRS)
    sys.exit(f"No video files ({', '.join(VIDEO_EXTS)}) found in {searched}")


def transcode(src: Path, out: Path) -> None:
    run(
        [
            "ffmpeg", "-i", str(src), "-map", "0",
            "-vf", "scale=-2:720",
            "-c:v", "libx264", "-c:a", "aac", "-c:s", "copy",
            "-crf", "23", "-preset", "slow",
            "-y", str(out),
        ],
        "Transcode to 720p H.264 (CRF 23, preset slow)",
    )


def main():
    print("Transcode -- compress and reencode video to standard format")

    src = select_input_file()

    out_dir = DATA / "transcoded"
    out_dir.mkdir(exist_ok=True)

    out = out_dir / f"{src.stem}.mp4"
    transcode(src, out)

    before = src.stat().st_size / 1e9
    after = out.stat().st_size / 1e9
    print(f"\nDone. {before:.2f} GB -> {after:.2f} GB -> {out}")


if __name__ == "__main__":
    main()
