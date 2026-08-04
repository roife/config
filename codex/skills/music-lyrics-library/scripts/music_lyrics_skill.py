#!/usr/bin/env python3
"""Run the library's consolidated music_lyrics.py entry point.

This thin launcher lets the skill operate on any folder containing the
consolidated entry point without duplicating the large, library-specific
implementation inside the skill package.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run music_lyrics.py from a library folder")
    parser.add_argument("--library", type=Path, default=Path.cwd())
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args()
    entry = ns.library.expanduser().resolve() / "music_lyrics.py"
    if not entry.is_file():
        raise SystemExit(f"missing consolidated entry point: {entry}")
    command = [sys.executable, str(entry), *ns.args]
    raise SystemExit(subprocess.run(command, cwd=entry.parent).returncode)


if __name__ == "__main__":
    main()
