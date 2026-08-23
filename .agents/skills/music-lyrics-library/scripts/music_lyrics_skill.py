#!/usr/bin/env python3
"""Run a library entry point, falling back to the bundled portable pipeline."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def default_media_root(library: Path) -> Path:
    apple_music = library / "Music" / "Media.localized" / "Music"
    return apple_music if apple_music.is_dir() else library


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the lyric workflow for a local music library")
    parser.add_argument("--library", type=Path, default=Path.cwd())
    parser.add_argument("--media-root", type=Path)
    parser.add_argument("--backup-root", type=Path)
    parser.add_argument("--entry", type=Path, help="override music_lyrics.py/pipeline entry point")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args()
    library = ns.library.expanduser().resolve()
    media_root = (
        ns.media_root.expanduser().resolve()
        if ns.media_root is not None
        else default_media_root(library)
    )
    if not library.is_dir():
        raise SystemExit(f"library directory does not exist: {library}")
    if not media_root.is_dir():
        raise SystemExit(f"media directory does not exist: {media_root}")

    local_entry = library / "music_lyrics.py"
    bundled_entry = Path(__file__).resolve().parent / "core" / "lyrics_pipeline.py"
    entry = ns.entry.expanduser().resolve() if ns.entry is not None else local_entry
    using_bundled = ns.entry is None and not local_entry.is_file()
    if using_bundled:
        entry = bundled_entry
    if not entry.is_file():
        raise SystemExit(f"pipeline entry point does not exist: {entry}")

    env = os.environ.copy()
    env["LYRICS_LIBRARY_ROOT"] = str(library)
    env["LYRICS_MEDIA_ROOT"] = str(media_root)
    if ns.backup_root is not None:
        env["LYRICS_BACKUP_ROOT"] = str(ns.backup_root.expanduser().resolve())

    if using_bundled:
        uv = shutil.which("uv")
        if not uv:
            raise SystemExit("the bundled pipeline requires uv; install it with mise")
        command = [
            uv,
            "run",
            "--no-project",
            "--python",
            "3.12",
            "--with",
            "mutagen",
            "--",
            "python",
            str(entry),
            *ns.args,
        ]
    else:
        command = [sys.executable, str(entry), *ns.args]
    raise SystemExit(subprocess.run(command, cwd=library, env=env).returncode)


if __name__ == "__main__":
    main()
