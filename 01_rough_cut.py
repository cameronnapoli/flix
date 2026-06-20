#!/usr/bin/env python3
"""
Cut a video into multiple rough segments based on user-inputted timestamps.

Segments are extracted with stream copy (fast, keyframe-aligned), so cut
points are not frame-accurate -- just close enough for a rough cut.
"""

import sys
from pathlib import Path
from lib.ffmpeg import cut_segment, fmt_time, parse_time, probe_duration


DATA = Path("data")
VIDEO_EXTS = (".mov", ".mp4", ".mkv")


def ask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    val = input(f"{prompt}{hint}: ").strip()
    return val if val else default


def confirm(msg: str) -> bool:
    return input(f"{msg} (y/n): ").strip().lower() == "y"


def select_input_file() -> Path:
    videos = sorted(p for p in DATA.iterdir() if p.suffix.lower() in VIDEO_EXTS)
    if not videos:
        sys.exit(f"No video files ({', '.join(VIDEO_EXTS)}) found in data/")

    video = videos[0]
    print(f"Found video: {video}  ({video.stat().st_size / 1e9:.2f} GB)")
    if not confirm("Use this file?"):
        sys.exit("Aborted.")
    return video


def main():
    print("Rough cut -- split a video into multiple segments")

    src = select_input_file()
    dur = probe_duration(src)
    print(f"Duration: {fmt_time(dur)} ({dur / 60:.1f} min)")

    out_dir = DATA / "rough_cut"
    out_dir.mkdir(exist_ok=True)

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

        out = out_dir / f"{src.stem}_segment{n:02d}{src.suffix}"
        cut_segment(src, start, end, out)
        print(f"  -> {out}")
        segments.append(out)
        n += 1

    if not segments:
        sys.exit("No segments created.")

    print(f"\nDone. {len(segments)} segment(s) written to {out_dir}/")
    for s in segments:
        print(f"  {s}")


if __name__ == "__main__":
    main()
