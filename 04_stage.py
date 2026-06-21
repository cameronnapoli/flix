#!/usr/bin/env python3
"""
Move the transcoded video into the upload directory.
"""

import argparse
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

from lib.cli import select_file
from lib.constants import DATA, VIDEO_EXTS

load_dotenv()


def parse_args():
    parser = argparse.ArgumentParser(description="Move the transcoded video into the upload directory.")
    parser.add_argument("-f", "--file", help="input video file (skip interactive selection)")
    return parser.parse_args()


def main():
    print("Stage -- move transcoded video to the upload directory")
    args = parse_args()

    src = select_file(args.file, DATA, VIDEO_EXTS, "video")

    upload_dir = Path(os.environ["VIDEO_UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)

    dest = upload_dir / src.name
    shutil.move(str(src), str(dest))

    print(f"\nDone. -> {dest}")


if __name__ == "__main__":
    main()
