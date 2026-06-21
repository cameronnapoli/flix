"""Input helpers shared by the flix pipeline scripts: CLI args first, interactive prompts as fallback."""

from __future__ import annotations

import sys
from pathlib import Path


def ask(prompt: str, default: str = "") -> str:
    """Prompt on stdin, returning `default` if the user enters nothing."""
    hint = f" [{default}]" if default else ""
    val = input(f"{prompt}{hint}: ").strip()
    return val if val else default


def confirm(msg: str) -> bool:
    return input(f"{msg} (y/n): ").strip().lower() == "y"


def select_file(
    candidate: str | None,
    dir: Path,
    exts: tuple[str, ...],
    kind: str,
) -> Path:
    """Resolve an input file: use `candidate` if given (e.g. from a --file flag),
    otherwise recursively list matching files under `dir` and let the user pick one."""
    if candidate is not None:
        path = Path(candidate)
        if not path.is_file():
            sys.exit(f"File not found: {path}")
        return path

    found = sorted(p for p in dir.rglob("*") if p.suffix.lower() in exts) if dir.exists() else []

    if not found:
        sys.exit(f"No {kind} files ({', '.join(exts)}) found in {dir}")

    if len(found) == 1:
        chosen = found[0]
        print(f"Found {kind}: {chosen}  ({chosen.stat().st_size / 1e9:.2f} GB)")
        if not confirm("Use this file?"):
            sys.exit("Aborted.")
        return chosen

    print(f"Multiple {kind} files found:")
    for i, p in enumerate(found, 1):
        print(f"  {i}. {p}  ({p.stat().st_size / 1e9:.2f} GB)")
    choice = ask(f"Select {kind} file (number)", default="1")
    if not choice.isdigit() or not 1 <= int(choice) <= len(found):
        sys.exit(f"Invalid selection: {choice}")
    return found[int(choice) - 1]
