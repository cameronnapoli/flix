#!/usr/bin/env python3
"""
FFmpeg experiment: file size and bitrate across CRF values and output resolutions.

Table axes:
  Rows    — output height (resolution)
  Columns — CRF value

Preset: superfast
"""

import json
import os
import subprocess
import time

INPUT = "data/luis_raw.mp4"

CRF_VALUES = [18, 23, 28, 33, 38]
HEIGHTS = [360, 480, 720, 1080]  # output heights in pixels


def encode(input_path: str, output_path: str, height: int, crf: int) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ss", str(10),
        "-to", str(20), # 10s clip
        "-vf", f"scale=-2:{height}",
        "-c:v", "libx264",
        "-c:a", "copy",
        "-preset", "superfast",
        "-crf", str(crf),
        "-an",          # no audio — isolate video size
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def get_bitrate_kbps(path: str) -> float:
    """Return average video bitrate in kbps via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            path,
        ],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            bit_rate = stream.get("bit_rate")
            if bit_rate:
                return int(bit_rate) / 1000
    # fall back to container-level bitrate
    result2 = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            path,
        ],
        check=True, capture_output=True, text=True,
    )
    fmt = json.loads(result2.stdout).get("format", {})
    return int(fmt.get("bit_rate", 0)) / 1000


def fmt_size(bytes_: int) -> str:
    if bytes_ >= 1_000_000:
        return f"{bytes_ / 1_000_000:.1f} MB"
    return f"{bytes_ / 1_000:.0f} KB"


def fmt_kbps(kbps: float) -> str:
    if kbps >= 1000:
        return f"{kbps / 1000:.2f} Mbps"
    return f"{kbps:.0f} kbps"


def fmt_elapsed(seconds: float) -> str:
    if seconds >= 60:
        m, s = divmod(seconds, 60)
        return f"{int(m)}m {s:.1f}s"
    return f"{seconds:.1f}s"


def print_table(title: str, rows: list[int], cols: list[int], data: dict, cell_fn) -> None:
    col_w = 14
    row_label_w = 8

    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")

    # header row
    header = f"{'':>{row_label_w}}" + "".join(f"{'CRF ' + str(c):>{col_w}}" for c in cols)
    print(header)
    print("-" * len(header))

    for r in rows:
        cells = "".join(f"{cell_fn(data[r][c]):>{col_w}}" for c in cols)
        print(f"{str(r) + 'p':>{row_label_w}}{cells}")


def main() -> None:
    if not os.path.exists(INPUT):
        raise FileNotFoundError(f"Input not found: {INPUT}")

    # results[height][crf] = {"size": int (bytes), "bitrate": float (kbps), "elapsed": float (s)}
    results: dict[int, dict[int, dict]] = {h: {} for h in HEIGHTS}

    total = len(HEIGHTS) * len(CRF_VALUES)
    done = 0

    out_dir = "out"
    os.makedirs(out_dir, exist_ok=True)

    for height in HEIGHTS:
        for crf in CRF_VALUES:
            done += 1
            label = f"{height}p  CRF {crf}"
            print(f"[{done}/{total}] Encoding {label} ...", flush=True)

            out = os.path.join(out_dir, f"{height}p_crf{crf}.mp4")
            t0 = time.perf_counter()
            encode(INPUT, out, height, crf)
            elapsed = time.perf_counter() - t0

            size = os.path.getsize(out)
            bitrate = get_bitrate_kbps(out)
            results[height][crf] = {"size": size, "bitrate": bitrate, "elapsed": elapsed}

            print(f"         → {fmt_size(size)}  {fmt_kbps(bitrate)}  {elapsed:.1f}s")

    print_table(
        "FILE SIZE",
        HEIGHTS, CRF_VALUES, results,
        lambda v: fmt_size(v["size"]),
    )

    print_table(
        "BITRATE",
        HEIGHTS, CRF_VALUES, results,
        lambda v: fmt_kbps(v["bitrate"]),
    )

    print_table(
        "ENCODING TIME",
        HEIGHTS, CRF_VALUES, results,
        lambda v: fmt_elapsed(v["elapsed"]),
    )

    print()


if __name__ == "__main__":
    main()
