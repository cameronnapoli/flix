#!/usr/bin/env python3
"""
Strip OBS metadata from a .mov or .mp4 and output a clean .mp4.

Usage:
    python clean.py <input_file> [output_file]

If output_file is omitted, the result is saved as <stem>_clean.mp4
in the same directory as the input.
"""

import subprocess
import sys
from pathlib import Path


def run(args: list[str], desc: str) -> None:
    print(f"\n[ffmpeg] {desc}")
    print("  " + " ".join(str(a) for a in args))
    result = subprocess.run(args, text=True, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(result.stderr[-3000:])
        sys.exit(f"ffmpeg failed (exit {result.returncode})")


def clean(input_path: Path, output_path: Path) -> None:
    run([
        "ffmpeg",
        "-i", str(input_path),
        "-c", "copy",
        "-map_metadata", "-1",
        "-metadata:s:v:0", "handler_name=VideoHandler",
        "-metadata:s:a:0", "handler_name=SoundHandler",
        "-metadata:s:v:0", "encoder=",
        "-y", str(output_path),
    ], f"Strip metadata: {input_path.name} → {output_path.name}")
    print(f"\nDone. Output: {output_path}")


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python clean.py <input_file> [output_file]")

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        sys.exit(f"File not found: {input_path}")

    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_name(f"{input_path.stem}_clean.mp4")

    clean(input_path, output_path)


if __name__ == "__main__":
    main()
