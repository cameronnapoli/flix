#!/usr/bin/env python3
"""
Move the transcoded video into the upload directory.
"""

import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA = Path("data")
VIDEO_EXTS = (".mov", ".mp4", ".mkv")
SEARCH_DIRS = (DATA / "transcoded", DATA)


def confirm(msg: str) -> bool:
    return input(f"{msg} (y/n): ").strip().lower() == "y"


def select_input_file() -> Path:
    for d in SEARCH_DIRS:
        if not d.exists():
            continue
        matches = sorted(p for p in d.iterdir() if p.suffix.lower() in VIDEO_EXTS)
        if matches:
            video = matches[0]
            print(f"Found video: {video}  ({video.stat().st_size / 1e9:.2f} GB)")
            if not confirm("Use this file?"):
                sys.exit("Aborted.")
            return video
    searched = ", ".join(str(d) for d in SEARCH_DIRS)
    sys.exit(f"No video files ({', '.join(VIDEO_EXTS)}) found in {searched}")


def main():
    print("Stage -- move transcoded video to the upload directory")

    src = select_input_file()

    upload_dir = Path(os.environ["VIDEO_UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)

    dest = upload_dir / src.name
    shutil.move(str(src), str(dest))

    print(f"\nDone. -> {dest}")


if __name__ == "__main__":
    main()
