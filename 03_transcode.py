#!/usr/bin/env python3
"""
Compress and reencode a video to the standard delivery format.

Scales to 720p and reencodes with H.264 (CRF 23, preset slow) + AAC audio,
copying subtitle streams through untouched.
"""

import argparse
from pathlib import Path

from lib.cli import select_file
from lib.constants import DATA, VIDEO_EXTS
from lib.ffmpeg import run


def parse_args():
    parser = argparse.ArgumentParser(description="Compress and reencode a video to the standard delivery format.")
    parser.add_argument("-f", "--file", help="input video file (skip interactive selection)")
    return parser.parse_args()


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
    args = parse_args()

    src = select_file(args.file, DATA, VIDEO_EXTS, "video")

    out_dir = DATA / "transcoded"
    out_dir.mkdir(exist_ok=True)

    out = out_dir / f"{src.stem}.mp4"
    transcode(src, out)

    before = src.stat().st_size / 1e9
    after = out.stat().st_size / 1e9
    print(f"\nDone. {before:.2f} GB -> {after:.2f} GB -> {out}")


if __name__ == "__main__":
    main()
