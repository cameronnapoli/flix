#!/usr/bin/env python3
"""
Process .mov + .xml subtitles into a final 1080p MP4.

Steps (run sequentially, each waits for user confirmation):
  1. Crop start  — trim leading content
  2. Crop end    — trim trailing content
  3. Combine     — merge trimmed video with shifted subtitles
  4. Compress    — re-encode to 1080p CRF 28
"""

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path("out")
OUT.mkdir(exist_ok=True)

def get_tick_rate(xml_path: Path) -> int:
    """Parse ttp:tickRate from the TTML root element."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    tick_rate = root.attrib.get("{http://www.w3.org/ns/ttml#parameter}tickRate", "10000000")
    return int(tick_rate)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(args: list[str], desc: str) -> None:
    print(f"\n[ffmpeg] {desc}")
    print("  " + " ".join(str(a) for a in args))
    result = subprocess.run(args, text=True, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(result.stderr[-3000:])
        sys.exit(f"ffmpeg failed (exit {result.returncode})")


def ask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    val = input(f"{prompt}{hint}: ").strip()
    return val if val else default


def confirm(msg: str) -> bool:
    return input(f"{msg} (y/n): ").strip().lower() == "y"


def parse_time(s: str) -> float:
    """Parse HH:MM:SS, MM:SS, or bare seconds into float seconds."""
    parts = s.split(":")
    parts = [float(p) for p in parts]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0]


def fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


# ---------------------------------------------------------------------------
# Subtitle handling
# ---------------------------------------------------------------------------

NS = {
    "tt": "http://www.w3.org/ns/ttml",
    "tts": "http://www.w3.org/ns/ttml#styling",
}


def ticks_to_sec(tick_str: str, tick_rate: int) -> float:
    return int(tick_str.rstrip("t")) / tick_rate


def sec_to_srt_time(sec: float) -> str:
    """Convert seconds to SRT timestamp format: HH:MM:SS,mmm"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def get_element_text(p: ET.Element) -> str:
    """Extract plain text from a <p> element, collapsing <br> to newlines and stripping tags."""
    parts = []

    def collect(el: ET.Element) -> None:
        if el.text:
            parts.append(el.text)
        for child in el:
            if child.tag.endswith("}br") or child.tag == "br":
                parts.append("\n")
            else:
                collect(child)
            if child.tail:
                parts.append(child.tail)

    collect(p)
    return "".join(parts).strip()


def ttml_to_srt(xml_path: Path, offset_sec: float, out_path: Path, tick_rate: int) -> None:
    """
    Parse TTML, shift timestamps by -offset_sec, and write an SRT file.
    Entries that end before the new start are dropped.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    entries = []
    for p in root.iter("{http://www.w3.org/ns/ttml}p"):
        begin = ticks_to_sec(p.attrib["begin"], tick_rate) - offset_sec
        end   = ticks_to_sec(p.attrib["end"],   tick_rate) - offset_sec
        if end <= 0:
            continue
        begin = max(0.0, begin)
        text = get_element_text(p)
        if text:
            entries.append((begin, end, text))

    with out_path.open("w", encoding="utf-8") as f:
        for i, (begin, end, text) in enumerate(entries, 1):
            f.write(f"{i}\n")
            f.write(f"{sec_to_srt_time(begin)} --> {sec_to_srt_time(end)}\n")
            f.write(f"{text}\n\n")

    dropped = sum(1 for p in root.iter("{http://www.w3.org/ns/ttml}p")) - len(entries)
    print(f"  SRT written to {out_path}  ({len(entries)} entries, {dropped} dropped)")


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step1_crop_start(mov: Path) -> tuple[float, Path]:
    print("\n" + "=" * 60)
    print("STEP 1 — Crop start of video")
    print("=" * 60)
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(mov)],
        capture_output=True, text=True,
    )
    dur = float(json.loads(probe.stdout)["format"]["duration"])
    print(f"Source: {mov}  (duration ≈ {dur:.1f}s / {dur/60:.1f} min)")
    t = parse_time(ask("  Enter start time to keep (HH:MM:SS or seconds)", "0"))
    out = OUT / "step1_start_cropped.mov"
    run([
        "ffmpeg",
        "-ss", str(t),
        "-i", str(mov),
        "-c", "copy",
        "-y", str(out),
    ], f"Trim from {fmt_time(t)}")
    print(f"\nOutput: {out}")
    return t, out


def step2_crop_end(prev: Path) -> Path:
    print("\n" + "=" * 60)
    print("STEP 2 — Crop end of video")
    print("=" * 60)
    # Get duration of trimmed file
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(prev)],
        capture_output=True, text=True,
    )
    dur = float(json.loads(probe.stdout)["format"]["duration"])
    print(f"Current duration: {dur:.1f}s / {dur/60:.1f} min  (end = {fmt_time(dur)})")
    t = parse_time(ask("  Enter end time to keep (HH:MM:SS or seconds)", fmt_time(dur)))
    out = OUT / "step2_end_cropped.mov"
    run([
        "ffmpeg",
        "-i", str(prev),
        "-t", str(t),
        "-c", "copy",
        "-y", str(out),
    ], f"Keep first {fmt_time(t)}")
    print(f"\nOutput: {out}")
    return out


def step3_convert_subtitles(xml: Path, start_offset: float, tick_rate: int) -> Path:
    print("\n" + "=" * 60)
    print("STEP 3 — Convert TTML to SRT")
    print("=" * 60)
    nudge = float(ask("  Additional sync nudge in seconds (positive = later, negative = earlier)", "0"))
    srt = OUT / "subtitles.srt"
    ttml_to_srt(xml, start_offset - nudge, srt, tick_rate)
    print(f"\nOutput: {srt}")
    return srt


def step4_embed_subtitles(prev: Path, srt: Path) -> Path:
    print("\n" + "=" * 60)
    print("STEP 4 — Embed subtitles")
    print("=" * 60)
    out = OUT / "step4_with_subs.mp4"
    run([
        "ffmpeg",
        "-i", str(prev),
        "-i", str(srt),
        "-c:v", "copy",
        "-c:a", "copy",
        "-c:s", "mov_text",
        "-metadata:s:s:0", "language=spa",
        "-y", str(out),
    ], "Mux video + subtitles into MP4")
    print(f"\nOutput: {out}")
    return out


def step5_compress(prev: Path, mov: Path) -> Path:
    print("\n" + "=" * 60)
    print("STEP 5 — Compress to 1080p")
    print("=" * 60)
    out = OUT / f"{mov.stem}_final.mp4"
    run([
        "ffmpeg",
        "-i", str(prev),
        "-vf", "scale=-2:1080",
        "-c:v", "libx264",
        "-crf", "28",
        "-preset", "fast",
        "-c:a", "copy",
        "-c:s", "copy",
        "-y", str(out),
    ], "Re-encode to 1080p CRF 28")
    print(f"\nOutput: {out}")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Video processing pipeline")

    # --- Input files ---
    while True:
        mov_input = ask("  MOV file path", "data/luis_miguel_s1_e1.mov")
        MOV = Path(mov_input)
        if MOV.exists():
            break
        print(f"  File not found: {MOV}")

    while True:
        xml_input = ask("  TTML subtitle file path", "data/luis_miguel_s1_e1.xml")
        XML = Path(xml_input)
        if XML.exists():
            break
        print(f"  File not found: {XML}")

    tick_rate = get_tick_rate(XML)

    print(f"\nFiles:")
    print(f"  Video : {MOV}  ({MOV.stat().st_size / 1e9:.2f} GB)")
    print(f"  Subs  : {XML}  (tickRate={tick_rate})")

    # Step 1
    start_offset, s1_out = step1_crop_start(MOV)
    if not confirm("\nStep 1 done. Inspect the output and continue to step 2?"):
        sys.exit("Stopped after step 1.")

    # Step 2
    s2_out = step2_crop_end(s1_out)
    if not confirm("\nStep 2 done. Inspect the output and continue to step 3?"):
        sys.exit("Stopped after step 2.")

    # Step 3
    s3_srt = step3_convert_subtitles(XML, start_offset, tick_rate)
    if not confirm("\nStep 3 done. Inspect the SRT and continue to step 4?"):
        sys.exit("Stopped after step 3.")

    # Step 4
    s4_out = step4_embed_subtitles(s2_out, s3_srt)
    if not confirm("\nStep 4 done. Inspect the output and continue to step 5?"):
        sys.exit("Stopped after step 4.")

    # Step 5
    s5_out = step5_compress(s4_out, MOV)
    print(f"\nAll done!  Final file: {s5_out}")

    # Cleanup
    intermediates = [s1_out, s2_out, s3_srt, s4_out]
    if confirm("\nDelete intermediate files?"):
        for f in intermediates:
            f.unlink(missing_ok=True)
            print(f"  Deleted {f}")
        print("Done.")


if __name__ == "__main__":
    main()
