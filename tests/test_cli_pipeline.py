"""
Integration tests that drive 01_rough_cut.py, 02_merge.py, and 03_transcode.py
as real CLI subprocesses (not imports), using --file/--segment/--ttml flags so
no interactive input is needed.

Each test runs in its own tmp dir with a tmp "data/" folder, so the real
data/ directory is never touched.

TestMergeCli makes real ElevenLabs + Anthropic API calls against the tiny
tests/fixtures/luis_miguel_clip.* fixture, and is skipped if the project's
.env doesn't have both API keys set.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
CLIP_MP4 = FIXTURES / "luis_miguel_clip.mp4"
CLIP_TTML = FIXTURES / "luis_miguel_clip.ttml"

_env = dotenv_values(ROOT / ".env")
_HAS_API_KEYS = bool(_env.get("ANTHROPIC_API_KEY")) and bool(_env.get("ELEVENLABS_API_KEY"))


def run_script(name: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / name), *args],
        cwd=cwd, capture_output=True, text=True, timeout=300,
    )


class TestRoughCutCli(unittest.TestCase):
    def test_cuts_segments_given_via_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            data.mkdir()
            video = data / "clip.mp4"
            shutil.copy(CLIP_MP4, video)

            result = run_script(
                "01_rough_cut.py",
                ["-f", str(video), "--segment", "0", "5", "--segment", "10", "15"],
                cwd=Path(tmp),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            segments = sorted((data / "rough_cut").glob("*.mp4"))
            self.assertEqual([p.name for p in segments], ["clip_segment01.mp4", "clip_segment02.mp4"])
            for seg in segments:
                self.assertGreater(seg.stat().st_size, 0)

    def test_missing_file_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_script("01_rough_cut.py", ["-f", "does-not-exist.mp4"], cwd=Path(tmp))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("File not found", result.stdout + result.stderr)


class TestTranscodeCli(unittest.TestCase):
    def test_transcodes_file_given_via_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            data.mkdir()
            video = data / "clip.mp4"
            shutil.copy(CLIP_MP4, video)

            result = run_script("03_transcode.py", ["-f", str(video)], cwd=Path(tmp))

            self.assertEqual(result.returncode, 0, result.stderr)
            out = data / "transcoded" / "clip.mp4"
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)


@unittest.skipUnless(_HAS_API_KEYS, "requires ANTHROPIC_API_KEY and ELEVENLABS_API_KEY in .env")
class TestMergeCli(unittest.TestCase):
    def test_merges_video_and_ttml_given_via_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            data.mkdir()
            video = data / "clip_video.mp4"
            ttml = data / "clip_ttml.ttml"
            shutil.copy(CLIP_MP4, video)
            shutil.copy(CLIP_TTML, ttml)

            result = run_script("02_merge.py", ["-f", str(video), "-t", str(ttml)], cwd=Path(tmp))

            self.assertEqual(result.returncode, 0, result.stderr)
            out_video = data / "merged" / "clip_video.mp4"
            out_srt = data / "merged" / "clip_ttml.srt"
            self.assertTrue(out_video.exists())
            self.assertTrue(out_srt.exists())
            self.assertGreater(out_srt.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
