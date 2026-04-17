#!/usr/bin/env python3
"""
FFmpeg experiment: file size and bitrate across presets (rows) and CRF values (columns).

One set of tables is printed per input file found in data/.

Clip: 10-second segment starting at t=10s, 720p output, no audio.
"""

import csv
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path("data")
OUT_DIR = Path("out/preset_crf_matrix")

CRF_VALUES = [18, 23, 28, 33, 38]
PRESETS = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow"]


def encode(input_path: str, output_path: str, preset: str, crf: int) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ss", "10",
        "-to", "20",          # 10-second clip
        "-vf", "scale=-2:720",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-an",                 # no audio — isolate video size
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def get_bitrate_kbps(path: str) -> float:
    """Return average video bitrate in kbps via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
        check=True, capture_output=True, text=True,
    )
    for stream in json.loads(result.stdout).get("streams", []):
        if stream.get("codec_type") == "video":
            bit_rate = stream.get("bit_rate")
            if bit_rate:
                return int(bit_rate) / 1000

    # fall back to container-level bitrate
    result2 = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
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


def print_table(title: str, rows: list[str], cols: list[int], data: dict, cell_fn) -> None:
    row_label_w = 12
    col_w = 14

    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")

    header = f"{'':>{row_label_w}}" + "".join(f"{'CRF ' + str(c):>{col_w}}" for c in cols)
    print(header)
    print("-" * len(header))

    for r in rows:
        cells = "".join(f"{cell_fn(data[r][c]):>{col_w}}" for c in cols)
        print(f"{r:>{row_label_w}}{cells}")


def run_for_file(input_path: Path, log_writer: csv.DictWriter) -> None:
    file_label = input_path.name
    print(f"\n{'#' * 70}")
    print(f"  INPUT: {file_label}")
    print(f"{'#' * 70}")

    # results[preset][crf] = {"size": int, "bitrate": float, "elapsed": float}
    results: dict[str, dict[int, dict]] = {p: {} for p in PRESETS}

    total = len(PRESETS) * len(CRF_VALUES)
    done = 0

    file_out_dir = OUT_DIR / input_path.stem
    file_out_dir.mkdir(parents=True, exist_ok=True)

    for preset in PRESETS:
        for crf in CRF_VALUES:
            done += 1
            label = f"{preset}  CRF {crf}"
            print(f"[{done:>{len(str(total))}}/{total}] Encoding {label} ...", flush=True)

            out = str(file_out_dir / f"{preset}_crf{crf}.mp4")
            t0 = time.perf_counter()
            encode(str(input_path), out, preset, crf)
            elapsed = time.perf_counter() - t0

            size = os.path.getsize(out)
            bitrate = get_bitrate_kbps(out)
            results[preset][crf] = {"size": size, "bitrate": bitrate, "elapsed": elapsed}

            print(f"         → {fmt_size(size)}  {fmt_kbps(bitrate)}  {fmt_elapsed(elapsed)}")

            log_writer.writerow({
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "input_file": file_label,
                "preset": preset,
                "crf": crf,
                "size_bytes": size,
                "bitrate_kbps": round(bitrate, 1),
                "elapsed_s": round(elapsed, 3),
            })

    print_table(
        f"FILE SIZE  [{file_label}]",
        PRESETS, CRF_VALUES, results,
        lambda v: fmt_size(v["size"]),
    )
    print_table(
        f"BITRATE  [{file_label}]",
        PRESETS, CRF_VALUES, results,
        lambda v: fmt_kbps(v["bitrate"]),
    )
    print_table(
        f"ENCODING TIME  [{file_label}]",
        PRESETS, CRF_VALUES, results,
        lambda v: fmt_elapsed(v["elapsed"]),
    )
    print()
    return results


def main() -> None:
    inputs = sorted(DATA_DIR.glob("*.mp4")) + sorted(DATA_DIR.glob("*.mov"))
    if not inputs:
        raise FileNotFoundError(f"No .mp4 or .mov files found in {DATA_DIR}/")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    log_path = OUT_DIR / "timings.csv"
    log_fields = ["timestamp", "input_file", "preset", "crf", "size_bytes", "bitrate_kbps", "elapsed_s"]
    with log_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=log_fields)
        writer.writeheader()
        for input_path in inputs:
            run_for_file(input_path, writer)
        f.flush()

    print(f"Timings saved to {log_path}")


if __name__ == "__main__":
    main()
