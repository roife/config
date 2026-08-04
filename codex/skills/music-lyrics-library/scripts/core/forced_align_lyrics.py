#!/usr/bin/env python3
"""Cache MLX Whisper word timestamps for lyric/audio forced alignment.

This helper never changes media tags.  It transcribes only timing candidates
selected by ``add_timed_lyrics.py`` and stores a compact, resumable word-time
cache.  The recognized text is used as an alignment signal; the final lyric
text always remains the user's already-cleaned embedded lyric.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mlx_whisper
from langdetect import DetectorFactory, detect


ROOT = Path("/Users/roifewu/Music")
MEDIA_ROOT = ROOT / "Music/Media.localized/Music"
PROPOSALS_PATH = ROOT / ".timed-lyrics-work/proposals.jsonl"
CACHE_ROOT = ROOT / ".timed-lyrics-work/whisper"
DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]")
KANA_RE = re.compile(r"[\u3040-\u30ff]")
HAN_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
HANGUL_RE = re.compile(r"[\uac00-\ud7af]")
CYRILLIC_RE = re.compile(r"[\u0400-\u052f]")
DetectorFactory.seed = 0


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def cache_path(relative_path: str) -> Path:
    digest = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()
    return CACHE_ROOT / f"{digest}.json"


def prompt_excerpt(lyrics: str) -> str:
    text = " ".join(line.strip() for line in lyrics.splitlines() if line.strip())
    if CJK_RE.search(text):
        return text[:210]
    words = text.split()
    return " ".join(words[:170])


def lyric_language(lyrics: str) -> str:
    """Infer language from the known lyric rather than unreliable sung-audio ID."""

    if HANGUL_RE.search(lyrics):
        return "ko"
    if KANA_RE.search(lyrics):
        return "ja"
    if HAN_RE.search(lyrics):
        return "zh"
    if CYRILLIC_RE.search(lyrics):
        return "ru"
    try:
        language = detect(lyrics)
    except Exception:
        language = "en"
    return {
        "zh-cn": "zh",
        "zh-tw": "zh",
        "no": "en",
        "af": "en",
    }.get(language, language)


def serializable_word(word: dict[str, Any]) -> dict[str, Any]:
    return {
        "word": str(word.get("word", "")),
        "start": round(float(word.get("start", 0.0)), 3),
        "end": round(float(word.get("end", word.get("start", 0.0))), 3),
        "probability": (
            round(float(word["probability"]), 5) if word.get("probability") is not None else None
        ),
    }


def transcribe_one(row: dict[str, Any], model: str) -> dict[str, Any]:
    relative_path = row["relative_path"]
    media_path = MEDIA_ROOT / relative_path
    if not media_path.is_file():
        raise FileNotFoundError(media_path)
    requested_language = lyric_language(row["current_lyrics"])
    result = mlx_whisper.transcribe(
        str(media_path),
        path_or_hf_repo=model,
        word_timestamps=True,
        initial_prompt=prompt_excerpt(row["current_lyrics"]),
        condition_on_previous_text=True,
        hallucination_silence_threshold=2.0,
        language=requested_language,
        verbose=None,
    )
    segments: list[dict[str, Any]] = []
    for segment in result.get("segments", []):
        segments.append(
            {
                "start": round(float(segment.get("start", 0.0)), 3),
                "end": round(float(segment.get("end", 0.0)), 3),
                "text": str(segment.get("text", "")),
                "avg_logprob": round(float(segment.get("avg_logprob", 0.0)), 5),
                "no_speech_prob": round(float(segment.get("no_speech_prob", 0.0)), 5),
                "words": [serializable_word(word) for word in segment.get("words", [])],
            }
        )
    return {
        "relative_path": relative_path,
        "title": row.get("metadata", {}).get("title", ""),
        "artist": row.get("metadata", {}).get("artist", ""),
        "duration": row.get("metadata", {}).get("duration", 0),
        "lyrics_sha256": row.get("current_lyrics_sha256", ""),
        "model": model,
        "requested_language": requested_language,
        "language": result.get("language", ""),
        "text": str(result.get("text", "")),
        "segments": segments,
        "word_count": sum(len(segment["words"]) for segment in segments),
        "transcribed_at": now_iso(),
    }


def command_transcribe(args: argparse.Namespace) -> None:
    rows = read_jsonl(PROPOSALS_PATH)
    selected: list[dict[str, Any]] = []
    allowed_statuses = set(args.status)
    for row in rows:
        if row.get("timing_status") not in allowed_statuses:
            continue
        if args.artist and args.artist.casefold() not in row.get("metadata", {}).get(
            "artist", ""
        ).casefold():
            continue
        if args.path_pattern and args.path_pattern.casefold() not in row["relative_path"].casefold():
            continue
        selected.append(row)
    if args.limit:
        selected = selected[: args.limit]
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"selected {len(selected)} tracks", flush=True)
    completed = 0
    skipped = 0
    failed = 0
    for index, row in enumerate(selected, 1):
        output = cache_path(row["relative_path"])
        if output.exists() and not args.force:
            try:
                existing = json.loads(output.read_text(encoding="utf-8"))
                if existing.get("lyrics_sha256") == row.get("current_lyrics_sha256"):
                    skipped += 1
                    print(
                        f"[{index}/{len(selected)}] cached {row['relative_path']}", flush=True
                    )
                    continue
            except Exception:
                pass
        print(f"[{index}/{len(selected)}] transcribe {row['relative_path']}", flush=True)
        try:
            result = transcribe_one(row, args.model)
            temporary = output.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary.replace(output)
            completed += 1
            print(
                f"  language={result['language']} words={result['word_count']}", flush=True
            )
        except Exception as exc:
            failed += 1
            error_path = output.with_suffix(".error.json")
            error_path.write_text(
                json.dumps(
                    {
                        "relative_path": row["relative_path"],
                        "error": str(exc),
                        "failed_at": now_iso(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"  ERROR: {exc}", file=sys.stderr, flush=True)
    print(
        json.dumps(
            {
                "selected": len(selected),
                "completed": completed,
                "cached": skipped,
                "failed": failed,
                "cache_root": str(CACHE_ROOT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--status",
        action="append",
        choices=["needs_timed_source", "review", "ready"],
        default=None,
        help="Repeat to select multiple statuses (default: needs_timed_source).",
    )
    parser.add_argument("--artist", default="")
    parser.add_argument("--path-pattern", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--force", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.status:
        args.status = ["needs_timed_source"]
    command_transcribe(args)


if __name__ == "__main__":
    main()
