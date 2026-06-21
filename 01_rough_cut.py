#!/usr/bin/env python3
"""
Cut a video into multiple rough segments based on user-inputted timestamps.

Segments are extracted with stream copy (fast, keyframe-aligned), so cut
points are not frame-accurate -- just close enough for a rough cut.
"""

import argparse
import sys

from lib.cli import ask, select_file
from lib.constants import DATA, VIDEO_EXTS
from lib.ffmpeg import cut_segment, fmt_time, parse_time, probe_duration


def parse_args():
    parser = argparse.ArgumentParser(description="Split a video into multiple rough segments.")
    parser.add_argument("-f", "--file", help="input video file (skip interactive selection)")
    parser.add_argument(
        "--segment",
        nargs="+",
        action="append",
        metavar=("START", "END"),
        help="START [END] time of a segment to cut (HH:MM:SS or seconds); "
        "repeat for multiple segments. If omitted, prompts interactively.",
    )
    return parser.parse_args()


def collect_segments_from_cli(specs: list[list[str]]) -> list[tuple[float, float | None]]:
    segments = []
    for spec in specs:
        if not 1 <= len(spec) <= 2:
            sys.exit(f"--segment takes 1 or 2 values (START [END]), got: {spec}")
        start = parse_time(spec[0])
        end = parse_time(spec[1]) if len(spec) == 2 else None
        segments.append((start, end))
    return segments


def collect_segments_interactively() -> list[tuple[float, float | None]]:
    segments = []
    n = 1
    while True:
        print(f"\n--- Segment {n} ---")
        start_s = ask("  Start time (HH:MM:SS or seconds, blank to stop)")
        if not start_s:
            break
        start = parse_time(start_s)
        end_s = ask("  End time (HH:MM:SS or seconds, blank for end of video)")
        end = parse_time(end_s) if end_s else None
        segments.append((start, end))
        n += 1
    return segments


def main():
    print("Rough cut -- split a video into multiple segments")
    args = parse_args()

    src = select_file(args.file, DATA, VIDEO_EXTS, "video")
    dur = probe_duration(src)
    print(f"Duration: {fmt_time(dur)} ({dur / 60:.1f} min)")

    out_dir = DATA / "rough_cut"
    out_dir.mkdir(exist_ok=True)

    times = collect_segments_from_cli(args.segment) if args.segment else collect_segments_interactively()

    segments = []
    for n, (start, end) in enumerate(times, 1):
        out = out_dir / f"{src.stem}_segment{n:02d}{src.suffix}"
        cut_segment(src, start, end, out)
        print(f"  -> {out}")
        segments.append(out)

    if not segments:
        sys.exit("No segments created.")

    print(f"\nDone. {len(segments)} segment(s) written to {out_dir}/")
    for s in segments:
        print(f"  {s}")


if __name__ == "__main__":
    main()
