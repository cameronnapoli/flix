import tempfile
import unittest
from pathlib import Path

from lib.ttml import Cue, _element_text, _fmt_srt_time, _parse_timestamp, parse_ttml, write_srt
from xml.etree import ElementTree as ET

FIXTURE = Path(__file__).parent / "fixtures" / "sample.ttml"


class TestFmtSrtTime(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(_fmt_srt_time(0), "00:00:00,000")

    def test_seconds_and_millis(self):
        self.assertEqual(_fmt_srt_time(9.5), "00:00:09,500")

    def test_minutes(self):
        self.assertEqual(_fmt_srt_time(75.25), "00:01:15,250")

    def test_hours(self):
        self.assertEqual(_fmt_srt_time(3661.001), "01:01:01,001")

    def test_negative_clamps_to_zero(self):
        self.assertEqual(_fmt_srt_time(-5), "00:00:00,000")


class TestParseTimestamp(unittest.TestCase):
    def test_ticks(self):
        # 10,000,000 ticks/sec, as used by Netflix TTML exports
        self.assertAlmostEqual(_parse_timestamp("29200000t", tick_rate=10_000_000, frame_rate=30), 2.92)

    def test_seconds_offset(self):
        self.assertEqual(_parse_timestamp("1.5s", tick_rate=1, frame_rate=30), 1.5)

    def test_clock_time(self):
        self.assertEqual(_parse_timestamp("00:01:02.500", tick_rate=1, frame_rate=30), 62.5)

    def test_clock_time_with_frames(self):
        self.assertEqual(_parse_timestamp("00:00:01:15", tick_rate=1, frame_rate=30), 1.5)

    def test_unrecognized_raises(self):
        with self.assertRaises(ValueError):
            _parse_timestamp("not-a-time", tick_rate=1, frame_rate=30)


class TestElementText(unittest.TestCase):
    def test_plain_text(self):
        elem = ET.fromstring("<p>hello</p>")
        self.assertEqual(_element_text(elem), "hello")

    def test_br_becomes_newline(self):
        elem = ET.fromstring("<p>line one<br/>line two</p>")
        self.assertEqual(_element_text(elem), "line one\nline two")

    def test_nested_span_text_included(self):
        elem = ET.fromstring('<p>[Hugo]<span style="style1">"Luis Miguel maltrata a fan.</span>.</p>')
        self.assertEqual(_element_text(elem), '[Hugo]"Luis Miguel maltrata a fan..')

    def test_br_nested_inside_span(self):
        elem = ET.fromstring('<p><span style="style1">line one<br/>line two</span></p>')
        self.assertEqual(_element_text(elem), "line one\nline two")

    def test_br_between_two_spans(self):
        elem = ET.fromstring(
            '<p><span style="style1">line one</span><br/><span style="style1">line two</span></p>'
        )
        self.assertEqual(_element_text(elem), "line one\nline two")

    def test_strips_surrounding_whitespace(self):
        elem = ET.fromstring("<p>  hello  </p>")
        self.assertEqual(_element_text(elem), "hello")


class TestParseTtml(unittest.TestCase):
    def test_parses_real_fixture(self):
        cues = parse_ttml(FIXTURE)
        self.assertEqual(len(cues), 8)
        self.assertAlmostEqual(cues[0].start, 2.92)
        self.assertAlmostEqual(cues[0].end, 7.0)
        self.assertEqual(cues[0].text, "[teléfono sonando]")

    def test_multiline_cue_from_br(self):
        cues = parse_ttml(FIXTURE)
        multiline = next(c for c in cues if "habla más despacio" in c.text)
        self.assertEqual(multiline.text, "A ver, Doc,\nhabla más despacio, no te entiendo.")

    def test_cue_with_nested_span(self):
        cues = parse_ttml(FIXTURE)
        spanned = next(c for c in cues if "Hugo" in c.text)
        self.assertEqual(spanned.text, '[Hugo]"Luis Miguel maltrata a fan..')

    def test_cue_with_music_note(self):
        cues = parse_ttml(FIXTURE)
        lyric = next(c for c in cues if "flash" in c.text)
        self.assertEqual(lyric.text, "♪ De pronto, flash ♪")

    def test_cue_with_br_between_spans(self):
        cues = parse_ttml(FIXTURE)
        spanned = next(c for c in cues if "Lucía" in c.text)
        self.assertEqual(spanned.text, "[Lucía] Ya te extrañaba.\n¿Qué hacés, cenando?")

    def test_sorted_by_start(self):
        cues = parse_ttml(FIXTURE)
        self.assertEqual([c.start for c in cues], sorted(c.start for c in cues))


class TestWriteSrt(unittest.TestCase):
    def test_round_trip_format(self):
        cues = [
            Cue(start=1.0, end=2.5, text="hello"),
            Cue(start=3.0, end=4.0, text="line one\nline two"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.srt"
            write_srt(cues, out)
            content = out.read_text(encoding="utf-8")

        self.assertEqual(
            content,
            "1\n00:00:01,000 --> 00:00:02,500\nhello\n\n"
            "2\n00:00:03,000 --> 00:00:04,000\nline one\nline two\n",
        )

    def test_unicode_passthrough(self):
        cues = [Cue(start=0.0, end=1.0, text="♪ De pronto, flash ♪")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.srt"
            write_srt(cues, out)
            content = out.read_text(encoding="utf-8")
        self.assertIn("♪ De pronto, flash ♪", content)


if __name__ == "__main__":
    unittest.main()
