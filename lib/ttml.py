"""Parse TTML subtitle files and write SRT output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


@dataclass
class Cue:
    start: float
    end: float
    text: str


TTP_NS = "{http://www.w3.org/ns/ttml#parameter}"
XML_NS = "{http://www.w3.org/XML/1998/namespace}"

# ISO 639-1 -> ISO 639-2/T, for the languages this pipeline has seen so far.
# MP4 'language' metadata (used by mov_text/QuickTime) expects the 3-letter form.
ISO_639_2 = {
    "es": "spa", "en": "eng", "pt": "por", "fr": "fre",
    "de": "ger", "it": "ita", "ja": "jpn", "ko": "kor",
    "zh": "chi", "ru": "rus", "ar": "ara",
}


def get_language(path: Path) -> str:
    """Return the ISO 639-2 language code declared by the TTML's xml:lang, or 'und'."""
    root = ET.parse(path).getroot()
    lang = root.get(f"{XML_NS}lang", "")
    return ISO_639_2.get(lang.split("-")[0].lower(), "und")


def _parse_timestamp(value: str, tick_rate: float, frame_rate: float) -> float:
    """Parse a TTML time expression: HH:MM:SS.mmm, HH:MM:SS:FF, Ns offset, or Nt ticks."""
    value = value.strip()
    if value.endswith("t"):
        return float(value[:-1]) / tick_rate
    if value.endswith("s"):
        return float(value[:-1])
    parts = value.split(":")
    if len(parts) == 4:
        h, m, s, f = parts
        return int(h) * 3600 + int(m) * 60 + int(s) + int(f) / frame_rate
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    raise ValueError(f"Unrecognized TTML timestamp: {value!r}")


def _flatten(elem: ET.Element) -> str:
    """Recursively join an element's text with its children's (e.g. <span>) text and tails."""
    parts = [elem.text or ""]
    for child in elem:
        if child.tag == "br" or child.tag.endswith("}br"):
            parts.append("\n")
        else:
            parts.append(_flatten(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _element_text(elem: ET.Element) -> str:
    """Flatten a <p> element's text, including nested inline elements, treating <br/> as newlines."""
    return _flatten(elem).strip()


def parse_ttml(path: Path) -> list[Cue]:
    """Parse a TTML file into a list of timed cues, sorted by start time."""
    root = ET.parse(path).getroot()
    tick_rate = float(root.get(f"{TTP_NS}tickRate", 1))
    frame_rate = float(root.get(f"{TTP_NS}frameRate", 30))
    cues = []
    for p in root.iter():
        if not (p.tag == "p" or p.tag.endswith("}p")):
            continue
        begin, end = p.get("begin"), p.get("end")
        if begin is None or end is None:
            continue
        text = _element_text(p)
        if text:
            cues.append(Cue(
                start=_parse_timestamp(begin, tick_rate, frame_rate),
                end=_parse_timestamp(end, tick_rate, frame_rate),
                text=text,
            ))
    return sorted(cues, key=lambda c: c.start)


def _fmt_srt_time(seconds: float) -> str:
    seconds = max(seconds, 0.0)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(cues: list[Cue], path: Path) -> None:
    """Write cues out as an SRT file."""
    lines = []
    for i, cue in enumerate(cues, start=1):
        lines.append(str(i))
        lines.append(f"{_fmt_srt_time(cue.start)} --> {_fmt_srt_time(cue.end)}")
        lines.append(cue.text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
