#!/usr/bin/env python3
"""Build, write, and verify synchronized LRC lyrics for the local media library.

The script is deliberately staged.  Commands before ``apply`` are read-only, and
``apply`` refuses to run unless every proposed lyric has passed structural
validation and a clone backup exists.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from mutagen import File as MutagenFile
from mutagen.id3 import USLT
from mutagen.mp4 import MP4
from mutagen.mp3 import MP3

import lyrics_pipeline as legacy


ROOT = Path(os.environ.get("LYRICS_LIBRARY_ROOT", Path.cwd())).expanduser().resolve()
MEDIA_ROOT = Path(
    os.environ.get("LYRICS_MEDIA_ROOT", ROOT / "Music/Media.localized/Music")
).expanduser().resolve()
WORK_ROOT = ROOT / ".timed-lyrics-work"
INVENTORY_PATH = WORK_ROOT / "current-inventory.jsonl"
SOURCE_MAP_PATH = WORK_ROOT / "source-map.jsonl"
PROPOSALS_PATH = WORK_ROOT / "proposals.jsonl"
FORCED_PROPOSALS_PATH = WORK_ROOT / "forced-proposals.jsonl"
FINAL_TIMING_DECISIONS_PATH = WORK_ROOT / "timing-final-decisions.jsonl"
FINAL_PROPOSALS_PATH = WORK_ROOT / "final-proposals.jsonl"
APPLY_STATE_PATH = WORK_ROOT / "apply-state.jsonl"
VERIFICATION_PATH = WORK_ROOT / "final-verification.jsonl"
WHISPER_CACHE_ROOT = WORK_ROOT / "whisper"
AUDIT_PATH = ROOT / "timed-lyrics-audit.jsonl"
AUDIT_MD_PATH = ROOT / "timed-lyrics-audit.md"
WRITE_BASELINE_PATH = WORK_ROOT / "write-baseline.jsonl"
BACKUP_INTEGRITY_PATH = WORK_ROOT / "backup-integrity.jsonl"
BACKUP_ROOT = Path(
    os.environ.get("LYRICS_TIMED_BACKUP_ROOT", ROOT / "Music-timed-lyrics-backup-20260730")
).expanduser().resolve()

OLD_AUDIT_PATH = ROOT / "lyrics-audit.jsonl"
NEW_PREPARED_PATH = ROOT / "M4A-lyrics-backup-20260729/.lyrics-work/prepared.jsonl"
POSTROCK_FINDINGS_PATH = (
    ROOT / ".lyrics-work/no-lyrics-postrock-review-20260730.jsonl"
)
EXTERNAL_TIMING_PATHS = [
    WORK_ROOT / "lyube-timed-sources.jsonl",
    WORK_ROOT / "other-timed-sources.jsonl",
]
DIRECT_REVIEW_B_PATH = WORK_ROOT / "direct-lrc-review-b.jsonl"
SKIPPED_EVENT_DECISIONS_PATH = WORK_ROOT / "skipped-event-decisions.jsonl"
DIRECT_SOURCE_DECISIONS_PATH = (
    WORK_ROOT / "direct-source-difference-decisions.jsonl"
)
FINAL_SYMBOL_CLEANUPS_PATH = WORK_ROOT / "final-symbol-cleanups.jsonl"
NEW_NO_LYRICS_CLASSIFICATION_PATH = (
    WORK_ROOT / "new-no-lyrics-classification.jsonl"
)

AUDIO_SUFFIXES = {".m4a", ".mp3"}
EXPECTED_MEDIA_COUNT = 940
EXPECTED_TARGET_COUNT = 656
TIME_TAG_RE = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")
CONCATENATED_FRACTION_RE = re.compile(r"\[(\d{1,3}):(\d{2})(\d{3,4})\]")
ANY_TIME_RE = re.compile(r"\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]")
META_TAG_RE = re.compile(r"^\[(?:ar|al|ti|by|offset|re|ve|length):", re.I)
FINAL_LRC_LINE_RE = re.compile(
    r"^\[(?P<minute>\d{2,3}):(?P<second>\d{2})\.(?P<millisecond>\d{3})\](?P<text>.+)$"
)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temp.replace(path)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def iter_audio() -> list[Path]:
    return sorted(
        (
            path
            for path in MEDIA_ROOT.rglob("*")
            if path.is_file() and path.suffix.casefold() in AUDIO_SUFFIXES
        ),
        key=lambda path: str(path).casefold(),
    )


def compact_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    return "".join(char for char in value if char.isalnum())


def identity_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    value = re.sub(r"\([^)]*(?:live|remaster|version|版|现场)[^)]*\)", "", value, flags=re.I)
    return "".join(char for char in value if char.isalnum())


def strip_lrc(value: str) -> str:
    lines: list[str] = []
    for raw_line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if META_TAG_RE.match(raw_line.strip()):
            continue
        line = ANY_TIME_RE.sub("", raw_line).rstrip()
        lines.append(line)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


@dataclass(frozen=True)
class LrcEvent:
    seconds: float
    text: str
    source_line: int


def parse_lrc(value: str) -> list[LrcEvent]:
    events: list[LrcEvent] = []
    for line_number, raw_line in enumerate(
        value.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1
    ):
        # A small number of otherwise good NetEase LRCs contain forms such as
        # ``[01:247000]`` for 01:24.700.  Normalize only the unambiguous
        # two-second-digits-plus-fraction form.
        raw_line = CONCATENATED_FRACTION_RE.sub(
            lambda match: f"[{match.group(1)}:{match.group(2)}.{match.group(3)[:3]}]",
            raw_line,
        )
        tags = list(TIME_TAG_RE.finditer(raw_line))
        if not tags:
            continue
        text_value = TIME_TAG_RE.sub("", raw_line).strip()
        if not text_value or META_TAG_RE.match(text_value):
            continue
        for tag in tags:
            minute = int(tag.group(1))
            second = int(tag.group(2))
            fraction_text = tag.group(3) or "0"
            fraction = int(fraction_text) / (10 ** len(fraction_text))
            events.append(
                LrcEvent(
                    seconds=minute * 60 + second + fraction,
                    text=text_value,
                    source_line=line_number,
                )
            )
    return sorted(events, key=lambda event: (event.seconds, event.source_line))


def line_similarity(left: str, right: str) -> float:
    left_nfkc = unicodedata.normalize("NFKC", left).strip().casefold()
    right_nfkc = unicodedata.normalize("NFKC", right).strip().casefold()
    if left_nfkc and left_nfkc == right_nfkc:
        return 1.0
    left_compact = compact_text(left)
    right_compact = compact_text(right)
    if not left_compact or not right_compact:
        return 0.0
    if left_compact == right_compact:
        return 1.0
    shorter, longer = sorted((left_compact, right_compact), key=len)
    containment = len(shorter) / len(longer) if shorter in longer else 0.0
    ratio = SequenceMatcher(None, left_compact, right_compact, autojunk=False).ratio()
    if containment >= 0.58:
        ratio = max(ratio, 0.82 + 0.16 * containment)
    return ratio


@dataclass
class Alignment:
    target_times: list[float | None]
    target_source_indices: list[list[int]]
    target_kinds: list[str]
    similarities: list[float]
    skipped_source_indices: list[int]


def align_lines(target_lines: list[str], events: list[LrcEvent]) -> Alignment:
    """Globally align cleaned lyric lines to timestamped source events."""

    n, m = len(target_lines), len(events)
    negative = -10**30
    dp = [[negative] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple[int, int, str, float] | None]] = [
        [None] * (m + 1) for _ in range(n + 1)
    ]
    dp[0][0] = 0.0

    def update(
        ni: int,
        nj: int,
        value: float,
        pi: int,
        pj: int,
        operation: str,
        similarity: float = 0.0,
    ) -> None:
        if value > dp[ni][nj]:
            dp[ni][nj] = value
            back[ni][nj] = (pi, pj, operation, similarity)

    for i in range(n + 1):
        for j in range(m + 1):
            base = dp[i][j]
            if base <= negative / 2:
                continue
            if j < m:
                update(i, j + 1, base - 0.055, i, j, "skip_source")
            if i < n:
                update(i + 1, j, base - 1.10, i, j, "skip_target")
            if i < n and j < m:
                similarity = line_similarity(target_lines[i], events[j].text)
                if similarity >= 0.28:
                    update(
                        i + 1,
                        j + 1,
                        base + 2.8 * similarity - 0.9,
                        i,
                        j,
                        "match_1_1",
                        similarity,
                    )
            if i < n and j + 1 < m:
                similarity = line_similarity(
                    target_lines[i], events[j].text + events[j + 1].text
                )
                if similarity >= 0.42:
                    update(
                        i + 1,
                        j + 2,
                        base + 2.75 * similarity - 0.98,
                        i,
                        j,
                        "match_1_2",
                        similarity,
                    )
            if i + 1 < n and j < m:
                similarity = line_similarity(
                    target_lines[i] + target_lines[i + 1], events[j].text
                )
                if similarity >= 0.42:
                    update(
                        i + 2,
                        j + 1,
                        base + 2.75 * similarity - 0.98,
                        i,
                        j,
                        "match_2_1",
                        similarity,
                    )

    target_times: list[float | None] = [None] * n
    source_indices: list[list[int]] = [[] for _ in range(n)]
    target_kinds = ["unmatched"] * n
    similarities = [0.0] * n
    skipped_sources: list[int] = []
    operations: list[tuple[int, int, int, int, str, float]] = []
    i, j = n, m
    while i or j:
        previous = back[i][j]
        if previous is None:
            raise RuntimeError(f"Alignment backtrack failed at {i},{j}")
        pi, pj, operation, similarity = previous
        operations.append((pi, pj, i, j, operation, similarity))
        i, j = pi, pj
    operations.reverse()

    for pi, pj, ni, nj, operation, similarity in operations:
        if operation == "skip_source":
            skipped_sources.append(pj)
        elif operation == "match_1_1":
            target_times[pi] = events[pj].seconds
            source_indices[pi] = [pj]
            target_kinds[pi] = operation
            similarities[pi] = similarity
        elif operation == "match_1_2":
            target_times[pi] = events[pj].seconds
            source_indices[pi] = [pj, pj + 1]
            target_kinds[pi] = operation
            similarities[pi] = similarity
        elif operation == "match_2_1":
            start = events[pj].seconds
            next_time = events[pj + 1].seconds if pj + 1 < len(events) else start + 4.0
            available = max(0.4, next_time - start)
            left_length = max(1, len(compact_text(target_lines[pi])))
            right_length = max(1, len(compact_text(target_lines[pi + 1])))
            split_time = start + available * left_length / (left_length + right_length)
            split_time = min(max(start + 0.10, split_time), max(start + 0.10, next_time - 0.05))
            target_times[pi] = start
            target_times[pi + 1] = split_time
            source_indices[pi] = [pj]
            source_indices[pi + 1] = [pj]
            target_kinds[pi] = operation
            target_kinds[pi + 1] = "match_2_1_interpolated"
            similarities[pi] = similarity
            similarities[pi + 1] = similarity

    # Fill genuinely unmatched target lines only provisionally.  They remain
    # explicitly flagged for external-source or audio-alignment review.
    matched = [index for index, value in enumerate(target_times) if value is not None]
    for index, value in enumerate(target_times):
        if value is not None:
            continue
        before = max((candidate for candidate in matched if candidate < index), default=None)
        after = min((candidate for candidate in matched if candidate > index), default=None)
        if before is not None and after is not None:
            fraction = (index - before) / (after - before)
            target_times[index] = float(target_times[before]) + (
                float(target_times[after]) - float(target_times[before])
            ) * fraction
        elif before is not None:
            target_times[index] = float(target_times[before]) + 2.0 * (index - before)
        elif after is not None:
            target_times[index] = max(0.0, float(target_times[after]) - 2.0 * (after - index))
        else:
            target_times[index] = 2.0 * index
        target_kinds[index] = "unmatched_interpolated"

    # LRC readers behave best with strictly increasing timestamps.
    last = -0.01
    for index, value in enumerate(target_times):
        assert value is not None
        if value <= last:
            target_times[index] = last + 0.01
            if "monotonic_adjusted" not in target_kinds[index]:
                target_kinds[index] += "+monotonic_adjusted"
        last = float(target_times[index])

    return Alignment(
        target_times=target_times,
        target_source_indices=source_indices,
        target_kinds=target_kinds,
        similarities=similarities,
        skipped_source_indices=skipped_sources,
    )


def format_lrc_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    minute, remainder = divmod(milliseconds, 60_000)
    second, millisecond = divmod(remainder, 1000)
    return f"[{minute:02d}:{second:02d}.{millisecond:03d}]"


def render_timed_lyrics(plain_lyrics: str, alignment: Alignment) -> str:
    output: list[str] = []
    target_index = 0
    for raw_line in plain_lyrics.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not raw_line.strip():
            if output and output[-1] != "":
                output.append("")
            continue
        timestamp = alignment.target_times[target_index]
        assert timestamp is not None
        output.append(format_lrc_time(timestamp) + raw_line)
        target_index += 1
    while output and output[-1] == "":
        output.pop()
    return "\n".join(output)


def timed_line_times(timed_lyrics: str) -> list[float]:
    values: list[float] = []
    for line_number, raw_line in enumerate(
        timed_lyrics.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1
    ):
        if not raw_line:
            continue
        match = FINAL_LRC_LINE_RE.fullmatch(raw_line)
        if not match:
            raise ValueError(f"line {line_number} is not strict LRC: {raw_line!r}")
        second = int(match.group("second"))
        if second >= 60:
            raise ValueError(f"line {line_number} has invalid seconds: {raw_line!r}")
        values.append(
            int(match.group("minute")) * 60
            + second
            + int(match.group("millisecond")) / 1000
        )
    return values


def override_timed_line_times(
    timed_lyrics: str, replacements: dict[str, Any] | dict[int, Any]
) -> str:
    normalized = timed_lyrics.replace("\r\n", "\n").replace("\r", "\n")
    output: list[str] = []
    lyric_index = 0
    numeric = {int(key): float(value) for key, value in replacements.items()}
    for raw_line in normalized.split("\n"):
        if not raw_line:
            output.append("")
            continue
        match = FINAL_LRC_LINE_RE.fullmatch(raw_line)
        if not match:
            raise ValueError(f"Cannot override malformed LRC line: {raw_line!r}")
        timestamp = numeric.get(lyric_index)
        if timestamp is None:
            output.append(raw_line)
        else:
            output.append(format_lrc_time(timestamp) + match.group("text"))
        lyric_index += 1
    return "\n".join(output).strip()


def render_times_for_plain(plain_lyrics: str, times: list[float]) -> str:
    line_count = sum(bool(line.strip()) for line in plain_lyrics.splitlines())
    if len(times) != line_count:
        raise ValueError(f"Timestamp count {len(times)} != lyric line count {line_count}")
    return render_timed_lyrics(
        plain_lyrics,
        Alignment(
            target_times=list(times),
            target_source_indices=[[] for _ in times],
            target_kinds=["manual_time"] * len(times),
            similarities=[1.0] * len(times),
            skipped_source_indices=[],
        ),
    )


def validate_final_timed_lyrics(
    timed_lyrics: str, plain_lyrics: str, duration: float
) -> dict[str, Any]:
    normalized = timed_lyrics.replace("\r\n", "\n").replace("\r", "\n").strip()
    normalized_plain = (
        plain_lyrics.replace("\r\n", "\n").replace("\r", "\n").strip()
    )
    times = timed_line_times(normalized)
    plain_line_count = sum(bool(line.strip()) for line in normalized_plain.splitlines())
    stripped = strip_lrc(normalized)
    issues: list[str] = []
    if len(times) != plain_line_count:
        issues.append(f"line_count:{len(times)}!={plain_line_count}")
    if stripped != normalized_plain:
        issues.append("stripped_text_mismatch")
    if any(right <= left for left, right in zip(times, times[1:])):
        issues.append("timestamps_not_strictly_increasing")
    if times and times[-1] > duration + 0.05:
        issues.append(f"timestamp_after_duration:{times[-1]:.3f}>{duration:.3f}")
    residual = legacy.residual_flags(stripped)
    if residual:
        issues.append("residual_non_lyric:" + ",".join(residual))
    return {
        "valid": not issues,
        "issues": issues,
        "line_count": len(times),
        "first_timestamp": round(times[0], 3) if times else None,
        "last_timestamp": round(times[-1], 3) if times else None,
        "strictly_increasing": not any(
            right <= left for left, right in zip(times, times[1:])
        ),
        "within_duration": not times or times[-1] <= duration + 0.05,
        "stripped_text_sha256": sha256_text(stripped),
    }


LEXICAL_RE = re.compile(
    r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]|[^\W_]+", re.UNICODE
)


def lexical_units(value: str) -> list[str]:
    units: list[str] = []
    for raw in LEXICAL_RE.findall(unicodedata.normalize("NFKC", value)):
        normalized = "".join(
            char
            for char in unicodedata.normalize("NFKD", raw).casefold().replace("ё", "е")
            if not unicodedata.combining(char) and char.isalnum()
        )
        if normalized:
            units.append(normalized)
    return units


def whisper_cache_path(relative_path: str) -> Path:
    return WHISPER_CACHE_ROOT / (
        hashlib.sha256(relative_path.encode("utf-8")).hexdigest() + ".json"
    )


def whisper_tokens(cache: dict[str, Any]) -> tuple[list[str], list[float]]:
    tokens: list[str] = []
    starts: list[float] = []
    for segment in cache.get("segments", []):
        for word in segment.get("words", []):
            units = lexical_units(str(word.get("word", "")))
            if not units:
                continue
            start = float(word.get("start", segment.get("start", 0.0)))
            end = float(word.get("end", start))
            width = max(0.0, end - start)
            for unit_index, unit in enumerate(units):
                tokens.append(unit)
                starts.append(start + width * unit_index / max(1, len(units)))
    return tokens, starts


def forced_alignment_from_whisper(
    plain_lyrics: str, cache: dict[str, Any], duration: float
) -> tuple[str, dict[str, Any]]:
    target_lines = [line.strip() for line in plain_lyrics.splitlines() if line.strip()]
    target_tokens: list[str] = []
    line_ranges: list[tuple[int, int]] = []
    punctuation_only: list[int] = []
    for line_index, line in enumerate(target_lines):
        start = len(target_tokens)
        units = lexical_units(line)
        target_tokens.extend(units)
        line_ranges.append((start, len(target_tokens)))
        if not units:
            punctuation_only.append(line_index)

    recognized_tokens, recognized_starts = whisper_tokens(cache)
    matcher = SequenceMatcher(
        None, target_tokens, recognized_tokens, autojunk=False
    )
    mapping: dict[int, int] = {}
    matched_token_count = 0
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            mapping[block.a + offset] = block.b + offset
        matched_token_count += block.size

    line_times: list[float | None] = []
    line_coverages: list[float] = []
    line_first_match_offsets: list[int | None] = []
    for start, end in line_ranges:
        if start == end:
            line_times.append(None)
            line_coverages.append(0.0)
            line_first_match_offsets.append(None)
            continue
        mapped = [(target, mapping[target]) for target in range(start, end) if target in mapping]
        line_coverages.append(len(mapped) / (end - start))
        if not mapped:
            line_times.append(None)
            line_first_match_offsets.append(None)
            continue
        first_target, first_recognized = mapped[0]
        leading_missing = first_target - start
        estimated = recognized_starts[first_recognized] - min(1.2, leading_missing * 0.18)
        line_times.append(max(0.0, estimated))
        line_first_match_offsets.append(leading_missing)

    mapped_lines = [index for index, value in enumerate(line_times) if value is not None]
    interpolated_lines: list[int] = []
    for index, value in enumerate(line_times):
        if value is not None:
            continue
        before = max((candidate for candidate in mapped_lines if candidate < index), default=None)
        after = min((candidate for candidate in mapped_lines if candidate > index), default=None)
        if before is not None and after is not None:
            fraction = (index - before) / (after - before)
            line_times[index] = float(line_times[before]) + (
                float(line_times[after]) - float(line_times[before])
            ) * fraction
        elif before is not None:
            line_times[index] = float(line_times[before]) + 2.0 * (index - before)
        elif after is not None:
            line_times[index] = max(
                0.0, float(line_times[after]) - 2.0 * (after - index)
            )
        else:
            line_times[index] = min(max(0.0, duration - 0.1), 2.0 * index)
        interpolated_lines.append(index)

    monotonic_adjusted: list[int] = []
    last = -0.05
    for index, value in enumerate(line_times):
        assert value is not None
        value = min(max(0.0, float(value)), max(0.0, duration - 0.05))
        if value <= last:
            value = min(max(0.0, duration - 0.05), last + 0.05)
            monotonic_adjusted.append(index)
        line_times[index] = value
        last = value

    alignment = Alignment(
        target_times=line_times,
        target_source_indices=[[] for _ in target_lines],
        target_kinds=[
            (
                "whisper_interpolated"
                if index in interpolated_lines
                else "whisper_word_alignment"
            )
            + ("+monotonic_adjusted" if index in monotonic_adjusted else "")
            for index in range(len(target_lines))
        ],
        similarities=line_coverages,
        skipped_source_indices=[],
    )
    timed = render_timed_lyrics(plain_lyrics, alignment)
    metrics = {
        "model": cache.get("model", ""),
        "language": cache.get("language", ""),
        "requested_language": cache.get("requested_language", ""),
        "target_token_count": len(target_tokens),
        "recognized_token_count": len(recognized_tokens),
        "matched_token_count": matched_token_count,
        "token_coverage": round(
            matched_token_count / max(1, len(target_tokens)), 4
        ),
        "line_count": len(target_lines),
        "direct_line_count": len(target_lines) - len(interpolated_lines),
        "direct_line_ratio": round(
            (len(target_lines) - len(interpolated_lines)) / max(1, len(target_lines)), 4
        ),
        "mean_line_coverage": round(
            sum(line_coverages) / max(1, len(line_coverages)), 4
        ),
        "line_coverages": [round(value, 4) for value in line_coverages],
        "line_first_match_offsets": line_first_match_offsets,
        "interpolated_lines": interpolated_lines,
        "punctuation_only_lines": punctuation_only,
        "monotonic_adjusted_lines": monotonic_adjusted,
        "latest_timestamp": round(max(float(value or 0) for value in line_times), 3),
        "stripped_matches_current": strip_lrc(timed) == plain_lyrics,
    }
    return timed, metrics


def command_whisper_align(args: argparse.Namespace) -> None:
    rows = read_jsonl(PROPOSALS_PATH)
    if not rows:
        raise RuntimeError("Run align first")
    output: list[dict[str, Any]] = []
    for row in rows:
        cache_path = whisper_cache_path(row["relative_path"])
        if not cache_path.exists() or row["timing_status"] not in args.status:
            output.append(row)
            continue
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        if cache.get("lyrics_sha256") != row.get("current_lyrics_sha256"):
            output.append({**row, "whisper_status": "stale_cache"})
            continue
        plain = strip_lrc(row["current_lyrics"])
        duration = float((row.get("metadata") or {}).get("duration") or 0)
        timed, metrics = forced_alignment_from_whisper(plain, cache, duration)
        accepted = (
            metrics["token_coverage"] >= args.minimum_token_coverage
            and metrics["direct_line_ratio"] >= args.minimum_direct_line_ratio
            and metrics["mean_line_coverage"] >= args.minimum_mean_line_coverage
            and not metrics["monotonic_adjusted_lines"]
            and metrics["stripped_matches_current"]
        )
        output.append(
            {
                **row,
                "whisper_status": "forced_ready" if accepted else "forced_review",
                "whisper_timed_lyrics": timed,
                "whisper_timed_lyrics_sha256": sha256_text(timed),
                "whisper_alignment": metrics,
            }
        )
    write_jsonl(FORCED_PROPOSALS_PATH, output)
    print(
        json.dumps(
            {
                "tracks": len(output),
                "whisper_statuses": Counter(
                    row.get("whisper_status", "not_run") for row in output
                ),
                "forced_proposals": str(FORCED_PROPOSALS_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def ffprobe_streams(path: Path) -> dict[str, Any]:
    process = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_type,codec_name,duration:format=duration",
            "-of",
            "json",
            str(path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode:
        raise RuntimeError(process.stderr.strip())
    parsed = json.loads(process.stdout)
    streams = [
        {
            "index": stream.get("index"),
            "codec_type": stream.get("codec_type"),
            "codec_name": stream.get("codec_name"),
            "duration": stream.get("duration"),
        }
        for stream in parsed.get("streams", [])
    ]
    return {
        "streams": streams,
        "format_duration": (parsed.get("format") or {}).get("duration"),
    }


def baseline_worker(relative_path: str) -> dict[str, Any]:
    path = MEDIA_ROOT / relative_path
    track = legacy.read_track(path, include_snapshot=True)
    return {
        "relative_path": relative_path,
        "lyrics_sha256": sha256_text(track.get("existing_lyrics", "")),
        "audio_payload_sha256": legacy.audio_payload_hash(path),
        "non_lyric_tag_hash": track["non_lyric_tag_hash"],
        "art": track["art"],
        "duration": track["duration"],
        "kind": track["kind"],
        "probe": ffprobe_streams(path),
        "captured_at": now_iso(),
    }


def command_baseline(args: argparse.Namespace) -> None:
    source_rows_current = read_jsonl(SOURCE_MAP_PATH)
    relative_paths = sorted(
        {row["relative_path"] for row in source_rows_current}, key=str.casefold
    )
    if not relative_paths:
        raise RuntimeError("No source map")
    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(baseline_worker, relative): relative for relative in relative_paths
        }
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            relative = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                raise RuntimeError(f"Baseline failed for {relative}: {exc}") from exc
            if index % 25 == 0 or index == len(relative_paths):
                print(f"baseline {index}/{len(relative_paths)}", flush=True)
    rows.sort(key=lambda row: row["relative_path"].casefold())
    write_jsonl(WRITE_BASELINE_PATH, rows)
    print(
        json.dumps(
            {
                "tracks": len(rows),
                "audio_hashes": sum(bool(row["audio_payload_sha256"]) for row in rows),
                "baseline": str(WRITE_BASELINE_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_include_preexisting_timed(args: argparse.Namespace) -> None:
    inventory = read_jsonl(INVENTORY_PATH)
    rows = read_jsonl(SOURCE_MAP_PATH)
    if len(inventory) != EXPECTED_MEDIA_COUNT:
        raise RuntimeError(
            f"Inventory must contain {EXPECTED_MEDIA_COUNT} rows, found {len(inventory)}"
        )
    by_path = {row["relative_path"]: row for row in rows}
    if len(by_path) != len(rows):
        raise RuntimeError("Source map contains duplicate paths")

    added: list[str] = []
    for track in inventory:
        relative = track["relative_path"]
        if relative in by_path or not track.get("timed"):
            continue
        timed = (
            str(track.get("lyrics") or "")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .strip()
        )
        plain = strip_lrc(timed)
        validation = validate_final_timed_lyrics(
            timed, plain, float(track.get("duration") or 0)
        )
        if not validation["valid"]:
            raise RuntimeError(
                f"Pre-existing timed lyric is not write-ready for {relative}: "
                f"{validation['issues']}"
            )
        row = {
            "relative_path": relative,
            "metadata": {
                key: track.get(key, "")
                for key in ("title", "artist", "album", "duration")
            },
            "current_lyrics": plain,
            "current_lyrics_sha256": sha256_text(plain),
            "status": "matched",
            "match_score": 2000,
            "second_score": None,
            "match_notes": [
                "preexisting_user_timed_lyrics",
                "strict_timeline_validated_and_preserved",
            ],
            "preexisting_timed": True,
            "original_embedded_timed_lyrics_sha256": sha256_text(timed),
            "source": {
                "source_set": "preexisting_embedded_timed_20260731",
                "source_key": sha256_text(relative),
                "source_path": relative,
                "title": track.get("title", ""),
                "artist": track.get("artist", ""),
                "album": track.get("album", ""),
                "duration": track.get("duration") or 0,
                "cleaned_lyrics": plain,
                "raw_lyrics": timed,
                "selected": {
                    "source": "preexisting_embedded_timed",
                    "source_id": relative,
                    "source_url": "",
                },
                "source_kind": "preexisting_embedded_timed",
            },
        }
        rows.append(row)
        by_path[relative] = row
        added.append(relative)

    rows.sort(key=lambda row: row["relative_path"].casefold())
    if len(rows) != EXPECTED_TARGET_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_TARGET_COUNT} total lyric targets after merge, "
            f"found {len(rows)}"
        )
    write_jsonl(SOURCE_MAP_PATH, rows)
    print(
        json.dumps(
            {
                "added_preexisting_timed": len(added),
                "total_targets": len(rows),
                "paths": added,
                "source_map": str(SOURCE_MAP_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_normalize_source_newlines(args: argparse.Namespace) -> None:
    rows = read_jsonl(SOURCE_MAP_PATH)
    changed: list[str] = []
    for row in rows:
        current = str(row.get("current_lyrics") or "")
        normalized = current.replace("\r\n", "\n").replace("\r", "\n")
        if normalized == current:
            continue
        row["current_lyrics"] = normalized
        row["current_lyrics_sha256"] = sha256_text(normalized)
        row.setdefault("manual_text_corrections", []).append(
            "normalized legacy CR/CRLF lyric newlines to LF"
        )
        changed.append(row["relative_path"])
    rows.sort(key=lambda row: row["relative_path"].casefold())
    write_jsonl(SOURCE_MAP_PATH, rows)
    print(
        json.dumps(
            {
                "changed_tracks": len(changed),
                "paths": changed,
                "source_map": str(SOURCE_MAP_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_assemble_final(args: argparse.Namespace) -> None:
    proposals = read_jsonl(PROPOSALS_PATH)
    forced_rows = {
        row["relative_path"]: row for row in read_jsonl(FORCED_PROPOSALS_PATH)
    }
    decisions = read_jsonl(FINAL_TIMING_DECISIONS_PATH)
    if len(proposals) != EXPECTED_TARGET_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_TARGET_COUNT} proposals, found {len(proposals)}"
        )
    decision_paths = [row["relative_path"] for row in decisions]
    duplicates = [
        path for path, count in Counter(decision_paths).items() if count > 1
    ]
    if duplicates:
        raise RuntimeError(f"Duplicate final timing decisions: {duplicates[:10]}")
    decision_by_path = {row["relative_path"]: row for row in decisions}

    output: list[dict[str, Any]] = []
    unresolved: list[str] = []
    methods = Counter()
    for row in proposals:
        relative = row["relative_path"]
        decision = decision_by_path.get(relative)
        method = ""
        timed = ""
        if decision and decision.get("timed_lyrics"):
            method = decision.get("method") or "manual_timed"
            timed = str(decision["timed_lyrics"]).strip()
        elif decision:
            method = decision.get("method") or decision.get("decision") or ""
            base_name = decision.get("base", "")
            if method in {"use_direct", "direct_lrc"} or base_name == "direct":
                timed = row.get("timed_lyrics", "")
                method = "direct_lrc_manual_review"
            elif method in {"use_whisper", "whisper"} or base_name == "whisper":
                timed = (forced_rows.get(relative) or {}).get(
                    "whisper_timed_lyrics", ""
                )
                method = "whisper_word_alignment_manual_review"
            if timed and decision.get("line_times"):
                timed = override_timed_line_times(timed, decision["line_times"])
                method += "+manual_line_overrides"
        elif row.get("timing_status") == "ready":
            timed = row.get("timed_lyrics", "")
            if row.get("preexisting_timed"):
                method = "preexisting_embedded_timed_preserved"
                expected_sha = row.get(
                    "original_embedded_timed_lyrics_sha256", ""
                )
                if not expected_sha or sha256_text(timed) != expected_sha:
                    raise RuntimeError(
                        f"Pre-existing timeline was not preserved byte-for-byte: "
                        f"{relative}"
                    )
            else:
                method = "direct_lrc"

        if not timed:
            unresolved.append(relative)
            continue
        plain = row["current_lyrics"].strip()
        timed_plain = strip_lrc(timed)
        if (
            timed_plain != plain
            and [line for line in timed_plain.splitlines() if line.strip()]
            == [line for line in plain.splitlines() if line.strip()]
        ):
            timed = render_times_for_plain(plain, timed_line_times(timed))
        validation = validate_final_timed_lyrics(
            timed, plain, float((row.get("metadata") or {}).get("duration") or 0)
        )
        if not validation["valid"]:
            raise RuntimeError(
                f"Invalid final timeline for {relative}: {validation['issues']}"
            )
        methods[method] += 1
        output.append(
            {
                **row,
                "timing_method": method,
                "timing_review": decision
                or (
                    {
                        "decision": "preexisting_embedded_timeline_preserved",
                        "validation": "strict_and_byte_exact",
                    }
                    if row.get("preexisting_timed")
                    else {
                        "decision": "automatic_direct_after_independent_batch_review"
                    }
                ),
                "final_timed_lyrics": timed,
                "final_timed_lyrics_sha256": sha256_text(timed),
                "final_validation": validation,
                "assembled_at": now_iso(),
            }
        )
    if unresolved:
        missing_path = WORK_ROOT / "final-unresolved.txt"
        missing_path.write_text("\n".join(unresolved) + "\n", encoding="utf-8")
        raise RuntimeError(
            f"{len(unresolved)} tracks still lack a final decision; see {missing_path}"
        )
    output.sort(key=lambda row: row["relative_path"].casefold())
    write_jsonl(FINAL_PROPOSALS_PATH, output)
    print(
        json.dumps(
            {
                "tracks": len(output),
                "methods": methods,
                "final_proposals": str(FINAL_PROPOSALS_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_align(args: argparse.Namespace) -> None:
    rows = read_jsonl(SOURCE_MAP_PATH)
    if not rows:
        raise RuntimeError("Run match-sources first")
    proposals: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        source = row.get("source") or {}
        raw = source.get("raw_lyrics") or ""
        if row.get("preexisting_timed"):
            timed = str(raw).strip()
            validation = validate_final_timed_lyrics(
                timed,
                row["current_lyrics"],
                float((row.get("metadata") or {}).get("duration") or 0),
            )
            if not validation["valid"]:
                raise RuntimeError(
                    f"Pre-existing timed lyric changed or became invalid for "
                    f"{row['relative_path']}: {validation['issues']}"
                )
            proposals.append(
                {
                    **row,
                    "timing_status": "ready",
                    "timed_lyrics": timed,
                    "timed_lyrics_sha256": sha256_text(timed),
                    "alignment": {
                        "method": "preserve_preexisting_embedded_timed",
                        "line_count": validation["line_count"],
                        "stripped_matches_current": True,
                    },
                }
            )
            continue
        events = parse_lrc(raw)
        if not events:
            proposals.append(
                {
                    **row,
                    "timing_status": "needs_timed_source",
                    "timed_lyrics": "",
                }
            )
            continue
        plain = strip_lrc(row["current_lyrics"])
        target_lines = [line.strip() for line in plain.splitlines() if line.strip()]
        alignment = align_lines(target_lines, events)
        timed = render_timed_lyrics(plain, alignment)
        low_similarity = [
            target_index
            for target_index, similarity in enumerate(alignment.similarities)
            if similarity < args.minimum_line_similarity
        ]
        approximate = [
            target_index
            for target_index, kind in enumerate(alignment.target_kinds)
            if "interpolated" in kind or "monotonic_adjusted" in kind
        ]
        stripped_match = strip_lrc(timed) == plain
        duration = float((row.get("metadata") or {}).get("duration") or 0)
        latest = max(float(value or 0) for value in alignment.target_times)
        timing_status = "ready"
        if (
            low_similarity
            or approximate
            or not stripped_match
            or latest > duration + args.duration_slack
        ):
            timing_status = "review"
        proposals.append(
            {
                **row,
                "timing_status": timing_status,
                "timed_lyrics": timed,
                "timed_lyrics_sha256": sha256_text(timed),
                "alignment": {
                    "target_line_count": len(target_lines),
                    "source_event_count": len(events),
                    "latest_timestamp": round(latest, 3),
                    "minimum_similarity": round(min(alignment.similarities, default=0), 4),
                    "mean_similarity": round(
                        sum(alignment.similarities) / max(1, len(alignment.similarities)), 4
                    ),
                    "low_similarity_lines": low_similarity,
                    "approximate_lines": approximate,
                    "target_kinds": alignment.target_kinds,
                    "similarities": [round(value, 4) for value in alignment.similarities],
                    "source_indices": alignment.target_source_indices,
                    "skipped_source_indices": alignment.skipped_source_indices,
                    "stripped_matches_current": stripped_match,
                },
            }
        )
        if index % 100 == 0:
            print(f"aligned {index}/{len(rows)}", flush=True)
    proposals.sort(key=lambda row: row["relative_path"].casefold())
    write_jsonl(PROPOSALS_PATH, proposals)
    print(
        json.dumps(
            {
                "tracks": len(proposals),
                "timing_statuses": Counter(row["timing_status"] for row in proposals),
                "ready_lines": sum(
                    (row.get("alignment") or {}).get("target_line_count", 0)
                    for row in proposals
                    if row["timing_status"] == "ready"
                ),
                "review_lines": sum(
                    len((row.get("alignment") or {}).get("approximate_lines", []))
                    for row in proposals
                ),
                "proposals": str(PROPOSALS_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_merge_timing_sources(args: argparse.Namespace) -> None:
    rows = read_jsonl(SOURCE_MAP_PATH)
    if not rows:
        raise RuntimeError("Run match-sources first")
    by_path = {row["relative_path"]: row for row in rows}
    accepted = 0
    ignored = Counter()
    for timing_path in EXTERNAL_TIMING_PATHS:
        if not timing_path.exists():
            ignored[f"missing_file:{timing_path.name}"] += 1
            continue
        for candidate in read_jsonl(timing_path):
            if candidate.get("status") != "found":
                ignored[candidate.get("status", "unknown")] += 1
                continue
            raw_lrc = candidate.get("raw_lrc") or ""
            if not ANY_TIME_RE.search(raw_lrc):
                ignored["found_without_timestamp"] += 1
                continue
            relative = candidate.get("relative_path", "")
            row = by_path.get(relative)
            if not row:
                ignored["path_not_in_source_map"] += 1
                continue
            source = dict(row.get("source") or {})
            previous_selected = source.get("selected")
            source["raw_lyrics"] = raw_lrc
            source["selected"] = {
                "source": candidate.get("source_name") or "external_sync_recheck",
                "source_id": str(candidate.get("source_id") or ""),
                "source_url": candidate.get("source_url") or "",
                "duration_difference": candidate.get("duration_delta"),
                "identity_notes": candidate.get("identity_notes", []),
                "lyrics_alignment_notes": candidate.get("lyrics_alignment_notes", []),
            }
            source["previous_selected"] = previous_selected
            row["source"] = source
            row["external_timing_source"] = {
                "result_file": timing_path.name,
                "status": "found",
                "source_id": candidate.get("source_id"),
                "source_url": candidate.get("source_url"),
                "identity_notes": candidate.get("identity_notes", []),
                "duration_delta": candidate.get("duration_delta"),
            }
            accepted += 1
    write_jsonl(SOURCE_MAP_PATH, sorted(rows, key=lambda row: row["relative_path"].casefold()))
    print(
        json.dumps(
            {
                "accepted": accepted,
                "ignored": ignored,
                "source_map": str(SOURCE_MAP_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def event_lyric_text(text: str, artist: str) -> str:
    cleaned, _transformations, _warnings = legacy.clean_lyrics(
        f"[00:00.000]{text}", "__timed_lyrics_nonmatching_title__", artist
    )
    return " ".join(line.strip() for line in cleaned.splitlines() if line.strip())


def paragraphize_events(items: list[tuple[float, str, bool]]) -> str:
    paragraphs: list[list[str]] = [[]]
    previous_time: float | None = None
    for timestamp, text_value, explicit_break in items:
        if (
            paragraphs[-1]
            and (
                explicit_break
                or (
                    previous_time is not None
                    and timestamp - previous_time >= 8.0
                    and len(paragraphs[-1]) >= 2
                )
            )
        ):
            paragraphs.append([])
        paragraphs[-1].append(text_value)
        previous_time = timestamp
    return "\n\n".join("\n".join(paragraph) for paragraph in paragraphs if paragraph)


def complete_source_lyrics(row: dict[str, Any], deduplicate_exact: bool = False) -> str:
    source = row.get("source") or {}
    artist = (row.get("metadata") or {}).get("artist", "")
    items: list[tuple[float, str, bool]] = []
    previous_key: tuple[float, str] | None = None
    for event in parse_lrc(source.get("raw_lyrics", "")):
        text_value = event_lyric_text(event.text, artist)
        if not text_value:
            continue
        key = (round(event.seconds, 3), compact_text(text_value))
        if deduplicate_exact and key == previous_key:
            continue
        items.append((event.seconds, text_value, False))
        previous_key = key
    return paragraphize_events(items)


def restore_source_events(row: dict[str, Any], restore_indices: set[int]) -> str:
    source = row.get("source") or {}
    events = parse_lrc(source.get("raw_lyrics", ""))
    plain = strip_lrc(row["current_lyrics"])
    target_lines = [line.strip() for line in plain.splitlines() if line.strip()]
    alignment = align_lines(target_lines, events)

    break_before: set[int] = set()
    next_is_break = False
    target_index = 0
    for line in plain.splitlines():
        if not line.strip():
            next_is_break = True
            continue
        if next_is_break and target_index:
            break_before.add(target_index)
        next_is_break = False
        target_index += 1

    anchored: dict[int, list[int]] = {}
    for target_index, indices in enumerate(alignment.target_source_indices):
        if indices:
            anchored.setdefault(min(indices), []).append(target_index)

    artist = (row.get("metadata") or {}).get("artist", "")
    items: list[tuple[float, str, bool]] = []
    emitted_targets: set[int] = set()
    for source_index, event in enumerate(events):
        targets = anchored.get(source_index, [])
        if targets:
            for target_index in targets:
                if target_index in emitted_targets:
                    continue
                items.append(
                    (
                        event.seconds,
                        target_lines[target_index],
                        target_index in break_before,
                    )
                )
                emitted_targets.add(target_index)
        elif source_index in restore_indices:
            text_value = event_lyric_text(event.text, artist)
            if text_value:
                items.append((event.seconds, text_value, False))

    # Retain any target line that an imperfect source alignment did not anchor.
    for target_index, text_value in enumerate(target_lines):
        if target_index not in emitted_targets:
            fallback_time = (
                float(alignment.target_times[target_index])
                if alignment.target_times[target_index] is not None
                else 0.0
            )
            items.append((fallback_time, text_value, target_index in break_before))
    items.sort(key=lambda item: item[0])
    return paragraphize_events(items)


def command_repair_text(args: argparse.Namespace) -> None:
    rows = read_jsonl(SOURCE_MAP_PATH)
    if not rows:
        raise RuntimeError("Run match-sources first")
    by_path = {row["relative_path"]: row for row in rows}
    corrections: dict[str, list[str]] = {}

    def replace(relative: str, new_lyrics: str, reason: str) -> None:
        row = by_path[relative]
        old = row["current_lyrics"]
        new_lyrics = new_lyrics.strip()
        if not new_lyrics:
            raise RuntimeError(f"Correction would empty lyric: {relative}")
        if new_lyrics == old.strip():
            return
        row.setdefault("pre_correction_lyrics", old)
        row.setdefault("pre_correction_lyrics_sha256", row["current_lyrics_sha256"])
        row["current_lyrics"] = new_lyrics
        row["current_lyrics_sha256"] = sha256_text(new_lyrics)
        row.setdefault("manual_text_corrections", []).append(reason)
        corrections.setdefault(relative, []).append(reason)

    # Restore source events independently flagged as actual sung title/repeat
    # lines that the older title-header cleaner removed.
    for review in read_jsonl(DIRECT_REVIEW_B_PATH):
        restore_indices: set[int] = set()
        credit_texts: set[str] = set()
        for issue in review.get("issues", []):
            if issue.get("code") == "skipped_probable_lyric_events":
                restore_indices.update(
                    int(item["source_index"]) for item in issue.get("occurrences", [])
                )
            elif issue.get("code") == "non_lyric_credit_in_current":
                credit_texts.update(
                    item["text"] for item in issue.get("occurrences", [])
                )
        relative = review["relative_path"]
        row = by_path.get(relative)
        if not row:
            continue
        if restore_indices:
            replace(
                relative,
                restore_source_events(row, restore_indices),
                f"restored {len(restore_indices)} independently verified sung title/repeat events",
            )
        if credit_texts:
            current = by_path[relative]["current_lyrics"]
            retained = [
                line for line in current.splitlines() if line.strip() not in credit_texts
            ]
            replace(
                relative,
                "\n".join(retained),
                f"removed {len(credit_texts)} residual performer/production credit lines",
            )

    # Five review tracks need more than inserting a skipped event.
    station = 'Любэ/Атас/09 Станция _Таганская_.m4a'
    replace(
        station,
        complete_source_lyrics(by_path[station], deduplicate_exact=True),
        "restored sung title interjections and removed exact duplicate 01:55 source event",
    )

    mother = "Любэ/Зона Любэ/09 Ты прости меня, мама.m4a"
    replace(
        mother,
        by_path[mother]["current_lyrics"].replace("]Мама", "Мама"),
        "removed malformed residual closing bracket before sung line",
    )

    tutoring = "老王乐队/吾十有五而志於學/02 补习班的门口高挂我的黑白照片.m4a"
    replace(
        tutoring,
        complete_source_lyrics(by_path[tutoring], deduplicate_exact=True),
        "removed two exact duplicate timestamp/text events while retaining real repeated outro",
    )

    love_end = "老王乐队/黄色的房子映照清晨的天空/02 我在爱情的尽头看见了你和我.m4a"
    love_lines = [
        line
        for line in by_path[love_end]["current_lyrics"].splitlines()
        if compact_text(line) != compact_text("、一森 Eason")
    ]
    replace(
        love_end,
        "\n".join(love_lines),
        "removed editing-engineer credit fragment",
    )

    burning = (
        "腰/他们说忘了摇滚有问题 (Forget Rock N Roll, We've Got a Problem)"
        "/2-02 你的街头在燃烧.m4a"
    )
    replace(
        burning,
        complete_source_lyrics(by_path[burning]),
        "restored omitted repeated verse and sung coda from exact timed source",
    )

    write_jsonl(SOURCE_MAP_PATH, sorted(rows, key=lambda row: row["relative_path"].casefold()))
    print(
        json.dumps(
            {
                "corrected_tracks": len(corrections),
                "corrections": corrections,
                "source_map": str(SOURCE_MAP_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_apply_skipped_decisions(args: argparse.Namespace) -> None:
    rows = read_jsonl(SOURCE_MAP_PATH)
    decisions = read_jsonl(SKIPPED_EVENT_DECISIONS_PATH)
    if not rows:
        raise RuntimeError("Run match-sources first")
    if not decisions:
        raise RuntimeError(f"No decisions at {SKIPPED_EVENT_DECISIONS_PATH}")

    by_path = {row["relative_path"]: row for row in rows}
    restore_by_path: dict[str, set[int]] = {}
    counts = Counter()
    for decision in decisions:
        verdict = decision.get("decision")
        if verdict not in {"restore", "keep_removed"}:
            raise RuntimeError(f"Unsupported skipped-event decision: {decision}")
        relative = decision["relative_path"]
        if relative not in by_path:
            raise RuntimeError(f"Decision path absent from source map: {relative}")
        counts[verdict] += 1
        if verdict == "restore":
            restore_by_path.setdefault(relative, set()).add(
                int(decision["source_index"])
            )

    changed: dict[str, int] = {}
    for relative, source_indices in restore_by_path.items():
        row = by_path[relative]
        old = row["current_lyrics"]
        rebuilt = restore_source_events(row, source_indices).strip()
        if not rebuilt:
            raise RuntimeError(f"Restoration emptied lyrics: {relative}")
        if rebuilt == old.strip():
            continue
        row.setdefault("pre_correction_lyrics", old)
        row.setdefault("pre_correction_lyrics_sha256", row["current_lyrics_sha256"])
        row["current_lyrics"] = rebuilt
        row["current_lyrics_sha256"] = sha256_text(rebuilt)
        reason = (
            f"restored {len(source_indices)} manually verified sung events "
            "that the title/noise cleaner had removed"
        )
        row.setdefault("manual_text_corrections", []).append(reason)
        row["skipped_event_review"] = {
            "decision_file": SKIPPED_EVENT_DECISIONS_PATH.name,
            "restored_source_indices": sorted(source_indices),
            "kept_removed_source_indices": sorted(
                int(item["source_index"])
                for item in decisions
                if item["relative_path"] == relative
                and item.get("decision") == "keep_removed"
            ),
        }
        changed[relative] = len(source_indices)

    write_jsonl(
        SOURCE_MAP_PATH, sorted(rows, key=lambda row: row["relative_path"].casefold())
    )
    print(
        json.dumps(
            {
                "reviewed_events": len(decisions),
                "decisions": counts,
                "changed_tracks": len(changed),
                "restored_events": sum(changed.values()),
                "source_map": str(SOURCE_MAP_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_apply_direct_source_decisions(args: argparse.Namespace) -> None:
    rows = read_jsonl(SOURCE_MAP_PATH)
    decisions = read_jsonl(DIRECT_SOURCE_DECISIONS_PATH)
    if not rows:
        raise RuntimeError("Run match-sources first")
    if not decisions:
        raise RuntimeError(f"No decisions at {DIRECT_SOURCE_DECISIONS_PATH}")

    by_path = {row["relative_path"]: row for row in rows}
    counts = Counter()
    changed: list[str] = []
    for decision in decisions:
        verdict = decision.get("decision")
        if verdict not in {"approve", "repair", "use_audio_alignment"}:
            raise RuntimeError(f"Unsupported direct-source decision: {decision}")
        relative = decision["relative_path"]
        row = by_path.get(relative)
        if row is None:
            raise RuntimeError(f"Decision path absent from source map: {relative}")
        counts[verdict] += 1
        row["direct_source_difference_review"] = {
            "decision_file": DIRECT_SOURCE_DECISIONS_PATH.name,
            "decision": verdict,
            "issues": decision.get("issues", []),
            "reason": decision.get("reason", ""),
            "evidence": decision.get("evidence", []),
        }
        if verdict != "repair":
            continue
        rebuilt = (decision.get("new_lyrics") or "").strip()
        if not rebuilt:
            raise RuntimeError(f"Repair lacks new_lyrics: {relative}")
        old = row["current_lyrics"]
        old_line_count = sum(bool(line.strip()) for line in old.splitlines())
        new_line_count = sum(bool(line.strip()) for line in rebuilt.splitlines())
        if old_line_count != new_line_count:
            raise RuntimeError(
                f"Repair changes line count for {relative}: "
                f"{old_line_count} -> {new_line_count}"
            )
        if rebuilt == old.strip():
            continue
        row.setdefault("pre_correction_lyrics", old)
        row.setdefault("pre_correction_lyrics_sha256", row["current_lyrics_sha256"])
        row["current_lyrics"] = rebuilt
        row["current_lyrics_sha256"] = sha256_text(rebuilt)
        row.setdefault("manual_text_corrections", []).append(
            "independent direct-source review: " + decision.get("reason", "")
        )
        changed.append(relative)

    write_jsonl(
        SOURCE_MAP_PATH, sorted(rows, key=lambda row: row["relative_path"].casefold())
    )
    print(
        json.dumps(
            {
                "reviewed_tracks": len(decisions),
                "decisions": counts,
                "changed_tracks": changed,
                "source_map": str(SOURCE_MAP_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_final_text_cleanups(args: argparse.Namespace) -> None:
    """Apply narrowly reviewed cleanups discovered during timing QA."""

    rows = read_jsonl(SOURCE_MAP_PATH)
    if not rows:
        raise RuntimeError("Run match-sources first")
    by_path = {row["relative_path"]: row for row in rows}
    changes: dict[str, str] = {}

    def replace(relative: str, rebuilt: str, reason: str) -> None:
        row = by_path[relative]
        rebuilt = rebuilt.strip()
        old = row["current_lyrics"]
        if not rebuilt:
            raise RuntimeError(f"Cleanup would empty lyrics: {relative}")
        if rebuilt == old.strip():
            return
        row.setdefault("pre_correction_lyrics", old)
        row.setdefault("pre_correction_lyrics_sha256", row["current_lyrics_sha256"])
        row["current_lyrics"] = rebuilt
        row["current_lyrics_sha256"] = sha256_text(rebuilt)
        row.setdefault("manual_text_corrections", []).append(reason)
        changes[relative] = reason

    border = "Compilations/Любэ专辑外歌曲/Граница.mp3"
    border_lyrics = "\n".join(
        line
        for line in by_path[border]["current_lyrics"].splitlines()
        if line.strip().casefold().rstrip(".:：") != "припев"
    )
    replace(
        border,
        border_lyrics,
        "removed the independently reviewed unsung section marker 'Припев.'",
    )

    station = 'Любэ/Атас/09 Станция _Таганская_.m4a'
    replace(
        station,
        complete_source_lyrics(by_path[station], deduplicate_exact=True),
        "removed an exact same-time duplicate LRC event at 01:55 while retaining the sung line",
    )

    write_jsonl(
        SOURCE_MAP_PATH, sorted(rows, key=lambda row: row["relative_path"].casefold())
    )
    print(
        json.dumps(
            {
                "changed_tracks": changes,
                "source_map": str(SOURCE_MAP_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_apply_review_texts(args: argparse.Namespace) -> None:
    rows = read_jsonl(SOURCE_MAP_PATH)
    if not rows:
        raise RuntimeError("Run match-sources first")
    by_path = {row["relative_path"]: row for row in rows}
    changed: dict[str, list[str]] = {}
    reviewed = 0
    for raw_path in args.file:
        review_path = Path(raw_path).expanduser()
        if not review_path.is_absolute():
            review_path = WORK_ROOT / review_path
        if not review_path.exists():
            raise RuntimeError(f"Review file does not exist: {review_path}")
        for review in read_jsonl(review_path):
            status = review.get("verdict") or review.get("status") or ""
            if status not in {
                "approve",
                "pass",
                "manual_repair",
                "repair",
                "completed",
                "repair_ready",
                "version_repaired_ready",
            }:
                continue
            relative = review.get("relative_path", "")
            row = by_path.get(relative)
            if row is None:
                raise RuntimeError(
                    f"Reviewed path is absent from source map: {relative}"
                )
            reviewed += 1
            candidate = (review.get("new_lyrics") or "").strip()
            if not candidate and review.get("timed_lyrics"):
                candidate = strip_lrc(str(review["timed_lyrics"])).strip()
            if not candidate:
                continue
            current = row["current_lyrics"].replace("\r\n", "\n").replace("\r", "\n").strip()
            candidate = candidate.replace("\r\n", "\n").replace("\r", "\n").strip()
            current_nonblank = [
                line for line in current.splitlines() if line.strip()
            ]
            candidate_nonblank = [
                line for line in candidate.splitlines() if line.strip()
            ]
            # A reviewer may render the same text with fewer paragraph breaks.
            # Preserve curated paragraphing unless the only difference is a
            # run of redundant blank lines, which strict LRC normalization
            # intentionally collapses.
            if candidate_nonblank == current_nonblank:
                canonical_current = re.sub(
                    r"\n(?:[ \t]*\n){2,}", "\n\n", current
                )
                canonical_candidate = re.sub(
                    r"\n(?:[ \t]*\n){2,}", "\n\n", candidate
                )
                if canonical_current != canonical_candidate:
                    continue
                candidate = canonical_current
                if candidate == current:
                    continue
            residual = legacy.residual_flags(candidate)
            if residual:
                raise RuntimeError(
                    f"Reviewed replacement contains residual noise for "
                    f"{relative}: {residual}"
                )
            row.setdefault("pre_correction_lyrics", row["current_lyrics"])
            row.setdefault(
                "pre_correction_lyrics_sha256", row["current_lyrics_sha256"]
            )
            row["current_lyrics"] = candidate
            row["current_lyrics_sha256"] = sha256_text(candidate)
            reason = (
                f"version/timing review {review_path.name}: "
                + "; ".join(review.get("issues", [])[:3])
            )
            row.setdefault("manual_text_corrections", []).append(reason)
            row.setdefault("timing_text_review_artifacts", []).append(
                review_path.name
            )
            changed.setdefault(relative, []).append(review_path.name)
    write_jsonl(
        SOURCE_MAP_PATH, sorted(rows, key=lambda row: row["relative_path"].casefold())
    )
    print(
        json.dumps(
            {
                "reviewed_complete_records": reviewed,
                "changed_tracks": len(changed),
                "changes": changed,
                "source_map": str(SOURCE_MAP_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_build_final_symbol_cleanups(args: argparse.Namespace) -> None:
    final_by_path = {
        row["relative_path"]: row for row in read_jsonl(FINAL_PROPOSALS_PATH)
    }
    cleanup_paths = {
        "Compilations/Cyberpunk Edgerunners Soundtrack Vol.1 (Ep1+2)/"
        "02 Major Crimes.m4a": "remove six isolated ellipsis placeholder lines",
        "刘欢/我在/01 我在.m4a": "remove isolated terminal ellipsis placeholder",
        "腰/相见恨晚/1-02 不只是南方.m4a": (
            "remove isolated ellipsis placeholder during instrumental gap"
        ),
        "黑豹/黑豹/05 靠近我.m4a": (
            "remove decorative dashes while preserving sung lyric text"
        ),
    }
    output: list[dict[str, Any]] = []
    for relative, reason in cleanup_paths.items():
        row = final_by_path.get(relative)
        if row is None:
            raise RuntimeError(f"Symbol-cleanup target absent: {relative}")
        removed: list[str] = []
        edited: list[dict[str, str]] = []
        rendered: list[str] = []
        for line in row["final_timed_lyrics"].splitlines():
            match = FINAL_LRC_LINE_RE.match(line.strip())
            if not match:
                rendered.append(line)
                continue
            text = match.group("text").strip()
            if re.fullmatch(r"(?:\.{2,}|…+)", text):
                removed.append(text)
                continue
            decoration = re.fullmatch(r"---\s*(.*?)\s*---", text)
            if decoration:
                replacement = decoration.group(1).strip()
                prefix = line[: line.index("]") + 1]
                rendered.append(prefix + replacement)
                edited.append({"before": text, "after": replacement})
                continue
            rendered.append(line)
        timed = re.sub(
            r"\n(?:[ \t]*\n){2,}", "\n\n", "\n".join(rendered).strip()
        )
        plain = strip_lrc(timed)
        validation = validate_final_timed_lyrics(
            timed,
            plain,
            float((row.get("metadata") or {}).get("duration") or 0),
        )
        if not validation["valid"]:
            raise RuntimeError(
                f"Symbol cleanup invalid for {relative}: "
                f"{validation['issues']}"
            )
        if not removed and not edited:
            raise RuntimeError(f"Symbol cleanup made no change: {relative}")
        output.append(
            {
                "relative_path": relative,
                "metadata": row.get("metadata", {}),
                "status": "manual_repair",
                "confidence": "high",
                "issues": [reason],
                "removed_non_lyric_lines": removed,
                "edited_lyric_lines": edited,
                "new_lyrics": plain,
                "new_lyrics_sha256": sha256_text(plain),
                "timed_lyrics": timed,
                "timed_lyrics_sha256": sha256_text(timed),
                "checks": validation,
                "review_basis": [
                    "independent final symbol scan",
                    "context review",
                    "preserved original timestamps for retained lyric lines",
                ],
            }
        )
    output.sort(key=lambda row: row["relative_path"].casefold())
    write_jsonl(FINAL_SYMBOL_CLEANUPS_PATH, output)
    print(
        json.dumps(
            {
                "tracks": len(output),
                "removed_lines": sum(
                    len(row["removed_non_lyric_lines"]) for row in output
                ),
                "edited_lines": sum(
                    len(row["edited_lyric_lines"]) for row in output
                ),
                "output": str(FINAL_SYMBOL_CLEANUPS_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_integrity_worker(relative: str) -> dict[str, Any]:
    current_path = MEDIA_ROOT / relative
    backup_path = BACKUP_ROOT / relative
    current_audio = MutagenFile(current_path, easy=False)
    backup_audio = MutagenFile(backup_path, easy=False)
    current_sha = sha256_file(current_path)
    backup_sha = sha256_file(backup_path)
    backup_stat = backup_path.stat()
    checks = {
        "backup_present": backup_path.is_file(),
        "whole_file_sha256_exact": current_sha == backup_sha,
        "current_parseable": current_audio is not None,
        "backup_parseable": backup_audio is not None,
        "kind_exact": type(current_audio) is type(backup_audio),
    }
    return {
        "relative_path": relative,
        "current_whole_file_sha256": current_sha,
        "backup_whole_file_sha256": backup_sha,
        "backup_size": backup_stat.st_size,
        "backup_mtime_ns": backup_stat.st_mtime_ns,
        "checks": checks,
        "passed": all(checks.values()),
        "verified_at": now_iso(),
    }


def command_backup_integrity(args: argparse.Namespace) -> None:
    current_paths = {
        str(path.relative_to(MEDIA_ROOT)) for path in iter_audio()
    }
    backup_paths = {
        str(path.relative_to(BACKUP_ROOT))
        for path in BACKUP_ROOT.rglob("*")
        if path.is_file() and path.suffix.casefold() in AUDIO_SUFFIXES
    }
    if len(current_paths) != EXPECTED_MEDIA_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_MEDIA_COUNT} current audio files, "
            f"found {len(current_paths)}"
        )
    if current_paths != backup_paths:
        raise RuntimeError("Current media and clone backup path sets differ")
    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(backup_integrity_worker, relative): relative
            for relative in sorted(current_paths, key=str.casefold)
        }
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            relative = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                rows.append(
                    {
                        "relative_path": relative,
                        "passed": False,
                        "error": str(exc),
                        "verified_at": now_iso(),
                    }
                )
            if index % 25 == 0 or index == len(futures):
                print(
                    f"backup integrity {index}/{len(futures)}",
                    flush=True,
                )
    rows.sort(key=lambda row: row["relative_path"].casefold())
    write_jsonl(BACKUP_INTEGRITY_PATH, rows)
    failures = [row for row in rows if not row.get("passed")]
    print(
        json.dumps(
            {
                "files": len(rows),
                "passed": len(rows) - len(failures),
                "failures": len(failures),
                "output": str(BACKUP_INTEGRITY_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if failures:
        raise RuntimeError(
            f"Backup integrity failed for {len(failures)} files"
        )


def apply_preflight_worker(
    final_row: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    relative = final_row["relative_path"]
    path = MEDIA_ROOT / relative
    current = legacy.read_track(path, include_snapshot=True)
    current_lyrics_sha = sha256_text(current["existing_lyrics"])
    expected_lyrics_hashes = {
        baseline["lyrics_sha256"],
        final_row["final_timed_lyrics_sha256"],
    }
    checks = {
        "lyrics_expected_state": current_lyrics_sha in expected_lyrics_hashes,
        "non_lyric_metadata": current["non_lyric_tag_hash"]
        == baseline["non_lyric_tag_hash"],
        "art": current["art"] == baseline["art"],
        "audio_payload": legacy.audio_payload_hash(path)
        == baseline["audio_payload_sha256"],
        "streams": ffprobe_streams(path) == baseline["probe"],
        "kind": current["kind"] == baseline["kind"],
    }
    return {
        "relative_path": relative,
        "lyrics_state": (
            "final"
            if current_lyrics_sha == final_row["final_timed_lyrics_sha256"]
            else "baseline"
            if current_lyrics_sha == baseline["lyrics_sha256"]
            else "unexpected"
        ),
        "checks": checks,
        "passed": all(checks.values()),
    }


def command_apply(args: argparse.Namespace) -> None:
    final_rows = read_jsonl(FINAL_PROPOSALS_PATH)
    baseline_rows = read_jsonl(WRITE_BASELINE_PATH)
    backup_integrity_rows = read_jsonl(BACKUP_INTEGRITY_PATH)
    if (
        len(final_rows) != EXPECTED_TARGET_COUNT
        or len(baseline_rows) != EXPECTED_TARGET_COUNT
    ):
        raise RuntimeError(
            "Final proposals and write baseline must each contain "
            f"{EXPECTED_TARGET_COUNT} rows"
        )
    for row in final_rows:
        relative = row["relative_path"]
        timed = str(row.get("final_timed_lyrics") or "")
        if sha256_text(timed) != row.get("final_timed_lyrics_sha256"):
            raise RuntimeError(f"Final timed lyric hash mismatch: {relative}")
        validation = validate_final_timed_lyrics(
            timed,
            row["current_lyrics"],
            float((row.get("metadata") or {}).get("duration") or 0),
        )
        if not validation["valid"]:
            raise RuntimeError(
                f"Final timed lyric failed apply validation for {relative}: "
                f"{validation['issues']}"
            )
    if len(backup_integrity_rows) != EXPECTED_MEDIA_COUNT:
        raise RuntimeError(
            "Backup integrity must contain "
            f"{EXPECTED_MEDIA_COUNT} verified rows"
        )
    current_paths = {
        str(path.relative_to(MEDIA_ROOT)) for path in iter_audio()
    }
    inventory_paths = {
        row["relative_path"] for row in read_jsonl(INVENTORY_PATH)
    }
    backup_paths = {
        str(path.relative_to(BACKUP_ROOT))
        for path in BACKUP_ROOT.rglob("*")
        if path.is_file() and path.suffix.casefold() in AUDIO_SUFFIXES
    }
    if len(current_paths) != EXPECTED_MEDIA_COUNT:
        raise RuntimeError(
            f"Current media library must contain {EXPECTED_MEDIA_COUNT} audio files, "
            f"found {len(current_paths)}"
        )
    if current_paths != inventory_paths:
        raise RuntimeError("Current media paths differ from the refreshed inventory")
    if current_paths != backup_paths:
        raise RuntimeError("Clone backup paths differ from the current media library")
    backup_integrity_by_path = {
        row["relative_path"]: row for row in backup_integrity_rows
    }
    if set(backup_integrity_by_path) != current_paths:
        raise RuntimeError("Backup integrity paths differ from the media library")
    for relative, integrity in backup_integrity_by_path.items():
        backup_stat = (BACKUP_ROOT / relative).stat()
        if (
            not integrity.get("passed")
            or integrity.get("current_whole_file_sha256")
            != integrity.get("backup_whole_file_sha256")
            or integrity.get("backup_size") != backup_stat.st_size
            or integrity.get("backup_mtime_ns") != backup_stat.st_mtime_ns
        ):
            raise RuntimeError(
                f"Clone backup integrity is stale or invalid: {relative}"
            )
    baseline_by_path = {row["relative_path"]: row for row in baseline_rows}
    if set(baseline_by_path) != {row["relative_path"] for row in final_rows}:
        raise RuntimeError("Final proposal paths differ from the write baseline")

    state_rows = read_jsonl(APPLY_STATE_PATH)
    state_by_path = {row["relative_path"]: row for row in state_rows}
    preflight: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                apply_preflight_worker,
                row,
                baseline_by_path[row["relative_path"]],
            ): row["relative_path"]
            for row in final_rows
        }
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            preflight.append(future.result())
            if index % 50 == 0 or index == len(futures):
                print(f"write preflight {index}/{len(futures)}", flush=True)
    failures = [row for row in preflight if not row["passed"]]
    write_jsonl(WORK_ROOT / "write-preflight.jsonl", sorted(
        preflight, key=lambda row: row["relative_path"].casefold()
    ))
    if failures:
        raise RuntimeError(f"Write preflight failed for {len(failures)} tracks")
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "preflight_only": True,
                    "targets": len(preflight),
                    "passed": len(preflight),
                    "output": str(WORK_ROOT / "write-preflight.jsonl"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    for index, row in enumerate(final_rows, 1):
        relative = row["relative_path"]
        path = MEDIA_ROOT / relative
        baseline = baseline_by_path[relative]
        previous_state = state_by_path.get(relative)
        current = legacy.read_track(path, include_snapshot=True)
        current_lyrics_sha = sha256_text(current["existing_lyrics"])
        current_checks = {
            "lyrics_expected_state": current_lyrics_sha
            in {
                baseline["lyrics_sha256"],
                row["final_timed_lyrics_sha256"],
            },
            "non_lyric_metadata": current["non_lyric_tag_hash"]
            == baseline["non_lyric_tag_hash"],
            "art": current["art"] == baseline["art"],
            "audio_payload": legacy.audio_payload_hash(path)
            == baseline["audio_payload_sha256"],
            "streams": ffprobe_streams(path) == baseline["probe"],
            "kind": current["kind"] == baseline["kind"],
        }
        if not all(current_checks.values()):
            raise RuntimeError(
                f"Track changed after write preflight: {relative}: {current_checks}"
            )
        if (
            previous_state
            and previous_state.get("status")
            in {"applied", "applied_recovered", "already_timed"}
            and current["existing_lyrics"] == row["final_timed_lyrics"]
        ):
            continue
        if current["existing_lyrics"] == row["final_timed_lyrics"]:
            recovered_status = (
                "already_timed"
                if baseline["lyrics_sha256"]
                == row["final_timed_lyrics_sha256"]
                else "applied_recovered"
            )
            state_by_path[relative] = {
                "relative_path": relative,
                "status": recovered_status,
                "final_timed_lyrics_sha256": row["final_timed_lyrics_sha256"],
                "checks": {**current_checks, "lyrics_exact": True},
                "applied_at": now_iso(),
            }
            write_jsonl(
                APPLY_STATE_PATH,
                sorted(
                    state_by_path.values(),
                    key=lambda item: item["relative_path"].casefold(),
                ),
            )
            continue
        if current_lyrics_sha != baseline["lyrics_sha256"]:
            raise RuntimeError(f"Lyrics changed after preflight: {relative}")
        legacy.set_embedded_lyrics(path, row["final_timed_lyrics"])
        after = legacy.read_track(path, include_snapshot=True)
        checks = {
            "lyrics_exact": after["existing_lyrics"] == row["final_timed_lyrics"],
            "non_lyric_metadata": after["non_lyric_tag_hash"]
            == baseline["non_lyric_tag_hash"],
            "art": after["art"] == baseline["art"],
            "audio_payload": legacy.audio_payload_hash(path)
            == baseline["audio_payload_sha256"],
            "streams": ffprobe_streams(path) == baseline["probe"],
            "kind": after["kind"] == baseline["kind"],
        }
        state_by_path[relative] = {
            "relative_path": relative,
            "status": "applied" if all(checks.values()) else "failed",
            "final_timed_lyrics_sha256": row["final_timed_lyrics_sha256"],
            "checks": checks,
            "applied_at": now_iso(),
        }
        write_jsonl(
            APPLY_STATE_PATH,
            sorted(state_by_path.values(), key=lambda item: item["relative_path"].casefold()),
        )
        if not all(checks.values()):
            raise RuntimeError(f"Immediate post-write verification failed: {relative}")
        if index % 25 == 0 or index == len(final_rows):
            print(f"write {index}/{len(final_rows)}", flush=True)
    print(
        json.dumps(
            {
                "applied": sum(
                    row.get("status")
                    in {"applied", "applied_recovered", "already_timed"}
                    for row in state_by_path.values()
                ),
                "written": sum(
                    row.get("status") in {"applied", "applied_recovered"}
                    for row in state_by_path.values()
                ),
                "preserved_preexisting": sum(
                    row.get("status") == "already_timed"
                    for row in state_by_path.values()
                ),
                "state": str(APPLY_STATE_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def final_verify_worker(
    inventory_row: dict[str, Any],
    final_row: dict[str, Any] | None,
    baseline: dict[str, Any] | None,
) -> dict[str, Any]:
    relative = inventory_row["relative_path"]
    path = MEDIA_ROOT / relative
    backup = BACKUP_ROOT / relative
    current = legacy.read_track(path, include_snapshot=True)
    if final_row is None:
        checks = {
            "backup_present": backup.is_file(),
            "whole_file_unchanged": backup.is_file()
            and sha256_file(path) == sha256_file(backup),
            "lyrics_absent": not current["existing_lyrics"].strip(),
        }
        return {
            "relative_path": relative,
            "status": "no_lyrics_unchanged",
            "checks": checks,
            "passed": all(checks.values()),
        }

    assert baseline is not None
    lyric_validation = validate_final_timed_lyrics(
        current["existing_lyrics"],
        final_row["current_lyrics"],
        float((final_row.get("metadata") or {}).get("duration") or 0),
    )
    checks = {
        "lyrics_exact": current["existing_lyrics"]
        == final_row["final_timed_lyrics"],
        "timeline_valid": lyric_validation["valid"],
        "non_lyric_metadata": current["non_lyric_tag_hash"]
        == baseline["non_lyric_tag_hash"],
        "art": current["art"] == baseline["art"],
        "audio_payload": legacy.audio_payload_hash(path)
        == baseline["audio_payload_sha256"],
        "streams": ffprobe_streams(path) == baseline["probe"],
    }
    if final_row.get("preexisting_timed"):
        checks.update(
            {
                "preexisting_lyrics_sha_preserved": sha256_text(
                    current["existing_lyrics"]
                )
                == inventory_row["lyrics_sha256"],
                "whole_file_unchanged": backup.is_file()
                and sha256_file(path) == sha256_file(backup),
            }
        )
    return {
        "relative_path": relative,
        "status": (
            "preexisting_timed_lyrics_preserved"
            if final_row.get("preexisting_timed")
            else "timed_lyrics_written"
        ),
        "checks": checks,
        "timeline": lyric_validation,
        "passed": all(checks.values()),
    }


def command_verify_final(args: argparse.Namespace) -> None:
    inventory = read_jsonl(INVENTORY_PATH)
    final_rows = read_jsonl(FINAL_PROPOSALS_PATH)
    baseline_rows = read_jsonl(WRITE_BASELINE_PATH)
    if len(inventory) != EXPECTED_MEDIA_COUNT:
        raise RuntimeError(
            f"Inventory must contain {EXPECTED_MEDIA_COUNT} rows, found {len(inventory)}"
        )
    if (
        len(final_rows) != EXPECTED_TARGET_COUNT
        or len(baseline_rows) != EXPECTED_TARGET_COUNT
    ):
        raise RuntimeError(
            "Final proposals and baseline must each contain "
            f"{EXPECTED_TARGET_COUNT} rows"
        )
    current_paths = {
        str(path.relative_to(MEDIA_ROOT)) for path in iter_audio()
    }
    inventory_paths = {row["relative_path"] for row in inventory}
    backup_paths = {
        str(path.relative_to(BACKUP_ROOT))
        for path in BACKUP_ROOT.rglob("*")
        if path.is_file() and path.suffix.casefold() in AUDIO_SUFFIXES
    }
    if current_paths != inventory_paths or current_paths != backup_paths:
        raise RuntimeError(
            "Current media, refreshed inventory, and clone backup path sets differ"
        )
    final_by_path = {row["relative_path"]: row for row in final_rows}
    baseline_by_path = {row["relative_path"]: row for row in baseline_rows}
    no_lyrics_review_by_path = {
        row["relative_path"]: row
        for row in read_jsonl(NEW_NO_LYRICS_CLASSIFICATION_PATH)
    }
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                final_verify_worker,
                inventory_row,
                final_by_path.get(inventory_row["relative_path"]),
                baseline_by_path.get(inventory_row["relative_path"]),
            ): inventory_row["relative_path"]
            for inventory_row in inventory
        }
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            relative = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(
                    {
                        "relative_path": relative,
                        "status": "verification_error",
                        "passed": False,
                        "error": str(exc),
                    }
                )
            if index % 50 == 0 or index == len(futures):
                print(f"final verify {index}/{len(futures)}", flush=True)
    results.sort(key=lambda row: row["relative_path"].casefold())
    write_jsonl(VERIFICATION_PATH, results)

    verification_by_path = {row["relative_path"]: row for row in results}
    audit_rows: list[dict[str, Any]] = []
    for inventory_row in inventory:
        relative = inventory_row["relative_path"]
        final_row = final_by_path.get(relative)
        verification = verification_by_path[relative]
        if final_row is None:
            audit_rows.append(
                {
                    "relative_path": relative,
                    "metadata": {
                        key: inventory_row.get(key, "")
                        for key in ("title", "artist", "album", "duration")
                    },
                    "action": "kept_without_lyrics",
                    "original_lyrics_present": False,
                    "final_lyrics_present": False,
                    "no_lyrics_review": no_lyrics_review_by_path.get(relative),
                    "verification": verification,
                }
            )
            continue
        source = final_row.get("source") or {}
        audit_rows.append(
            {
                "relative_path": relative,
                "metadata": final_row.get("metadata", {}),
                "action": (
                    "preserved_preexisting_timed_lyrics"
                    if final_row.get("preexisting_timed")
                    else (
                        "added_timed_lyrics"
                        if final_row.get("originally_empty")
                        else "replaced_plain_lyrics_with_timed_lyrics"
                    )
                ),
                "timing_method": final_row["timing_method"],
                "source": source.get("selected"),
                "match_notes": final_row.get("match_notes", []),
                "manual_text_corrections": final_row.get(
                    "manual_text_corrections", []
                ),
                "timing_review": final_row.get("timing_review"),
                "original_lyrics_sha256": baseline_by_path[relative][
                    "lyrics_sha256"
                ],
                "final_timed_lyrics_sha256": final_row[
                    "final_timed_lyrics_sha256"
                ],
                "line_count": final_row["final_validation"]["line_count"],
                "verification": verification,
            }
        )
    write_jsonl(AUDIT_PATH, audit_rows)
    failures = [row for row in results if not row.get("passed")]
    method_counts = Counter(
        row["timing_method"] for row in final_rows
    )
    action_counts = Counter(row["action"] for row in audit_rows)
    with AUDIT_MD_PATH.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Timed lyrics audit\n\n")
        fh.write(f"- Generated: {now_iso()}\n")
        fh.write(f"- Media files: {len(inventory)}\n")
        fh.write(f"- Tracks with validated timed lyrics: {len(final_rows)}\n")
        fh.write(
            "- Timed lyrics newly written: "
            f"{action_counts['added_timed_lyrics'] + action_counts['replaced_plain_lyrics_with_timed_lyrics']}\n"
        )
        fh.write(
            "- Pre-existing timed lyrics preserved: "
            f"{action_counts['preserved_preexisting_timed_lyrics']}\n"
        )
        fh.write(f"- Kept without lyrics: {len(inventory) - len(final_rows)}\n")
        fh.write(
            "- Newly added no-lyrics tracks independently classified: "
            f"{len(no_lyrics_review_by_path)}\n"
        )
        fh.write(f"- Verification failures: {len(failures)}\n")
        fh.write(f"- Clone backup retained: `{BACKUP_ROOT}`\n\n")
        fh.write("## Timing methods\n\n")
        for method, count in sorted(method_counts.items()):
            fh.write(f"- `{method}`: {count}\n")
        fh.write("\n## Actions\n\n")
        for action, count in sorted(action_counts.items()):
            fh.write(f"- `{action}`: {count}\n")
        if failures:
            fh.write("\n## Failures\n\n")
            for failure in failures:
                fh.write(
                    f"- `{failure['relative_path']}`: "
                    f"{failure.get('error') or failure.get('checks')}\n"
                )
    print(
        json.dumps(
            {
                "files": len(results),
                "passed": len(results) - len(failures),
                "failures": len(failures),
                "audit_jsonl": str(AUDIT_PATH),
                "audit_md": str(AUDIT_MD_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if failures:
        raise RuntimeError(f"Final verification found {len(failures)} failures")


def read_basic(path: Path) -> dict[str, Any]:
    row = legacy.read_track(path, include_snapshot=False)
    lyric = row.pop("existing_lyrics", "")
    row.update(
        {
            "has_lyrics": bool(lyric.strip()),
            "lyrics": lyric,
            "lyrics_sha256": sha256_text(lyric),
            "timed": bool(ANY_TIME_RE.search(lyric)),
            "inventoried_at": now_iso(),
        }
    )
    return row


def command_inventory(args: argparse.Namespace) -> None:
    paths = iter_audio()
    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(read_basic, path): path for path in paths}
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            path = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                raise RuntimeError(f"Cannot inventory {path}: {exc}") from exc
            if index % 50 == 0 or index == len(paths):
                print(f"inventory {index}/{len(paths)}", flush=True)
    rows.sort(key=lambda row: row["relative_path"].casefold())
    write_jsonl(INVENTORY_PATH, rows)
    print(
        json.dumps(
            {
                "files": len(rows),
                "with_lyrics": sum(row["has_lyrics"] for row in rows),
                "without_lyrics": sum(not row["has_lyrics"] for row in rows),
                "already_timed": sum(row["timed"] for row in rows),
                "formats": Counter(row["kind"] for row in rows),
                "inventory": str(INVENTORY_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def source_rows() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in read_jsonl(OLD_AUDIT_PATH):
        cleaned = (row.get("cleaned_lyrics") or "").strip()
        if not cleaned:
            continue
        meta = row.get("metadata") or {}
        selected = row.get("selected") or {}
        result.append(
            {
                "source_set": "legacy_audit",
                "source_key": row.get("key"),
                "source_path": row.get("relative_path"),
                "title": meta.get("title", ""),
                "artist": meta.get("artist", ""),
                "album": meta.get("album", ""),
                "duration": meta.get("duration") or 0,
                "cleaned_lyrics": cleaned,
                "raw_lyrics": row.get("original_lyrics") or "",
                "selected": selected,
                "source_kind": row.get("source_kind", ""),
            }
        )
    for index, row in enumerate(read_jsonl(NEW_PREPARED_PATH)):
        cleaned = (row.get("cleaned_lyrics") or "").strip()
        if not cleaned:
            continue
        meta = row.get("metadata") or {}
        result.append(
            {
                "source_set": "m4a_import_20260729",
                "source_key": f"m4a-{index:03d}",
                "source_path": row.get("file") or row.get("path") or "",
                "title": meta.get("title", ""),
                "artist": meta.get("artist", ""),
                "album": meta.get("album", ""),
                "duration": meta.get("duration") or 0,
                "cleaned_lyrics": cleaned,
                "raw_lyrics": row.get("raw_lyrics") or "",
                "selected": {
                    "source": "netease",
                    "source_id": str(row.get("netease_id") or ""),
                    "source_url": row.get("source_url") or "",
                },
                "source_kind": "netease",
            }
        )
    return result


def source_match_score(track: dict[str, Any], source: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    notes: list[str] = []
    track_plain = compact_text(strip_lrc(track["lyrics"]))
    source_plain = compact_text(source["cleaned_lyrics"])
    if track_plain and source_plain:
        ratio = SequenceMatcher(None, track_plain, source_plain, autojunk=False).ratio()
        score += ratio * 300
        notes.append(f"lyrics_ratio={ratio:.4f}")
        if track_plain == source_plain:
            score += 1000
            notes.append("lyrics_exact")
    title_ratio = SequenceMatcher(
        None, identity_text(track.get("title", "")), identity_text(source.get("title", "")), autojunk=False
    ).ratio()
    artist_ratio = SequenceMatcher(
        None, identity_text(track.get("artist", "")), identity_text(source.get("artist", "")), autojunk=False
    ).ratio()
    album_ratio = SequenceMatcher(
        None, identity_text(track.get("album", "")), identity_text(source.get("album", "")), autojunk=False
    ).ratio()
    score += 160 * title_ratio + 100 * artist_ratio + 25 * album_ratio
    duration_delta = abs(float(track.get("duration") or 0) - float(source.get("duration") or 0))
    score += max(0.0, 80.0 - duration_delta * 8.0)
    notes.extend(
        [
            f"title_ratio={title_ratio:.3f}",
            f"artist_ratio={artist_ratio:.3f}",
            f"album_ratio={album_ratio:.3f}",
            f"duration_delta={duration_delta:.3f}",
        ]
    )
    if track.get("relative_path") == source.get("source_path"):
        score += 500
        notes.append("path_exact")
    return score, notes


def command_match_sources(args: argparse.Namespace) -> None:
    inventory = read_jsonl(INVENTORY_PATH)
    if not inventory:
        raise RuntimeError("Run inventory first")
    sources = source_rows()
    for source in sources:
        source["_lyrics_compact"] = compact_text(source["cleaned_lyrics"])
        source["_title_identity"] = identity_text(source.get("title", ""))
        source["_artist_identity"] = identity_text(source.get("artist", ""))
    lyrics_index: dict[str, list[dict[str, Any]]] = {}
    path_index: dict[str, list[dict[str, Any]]] = {}
    for source in sources:
        lyrics_index.setdefault(source["_lyrics_compact"], []).append(source)
        path_index.setdefault(source.get("source_path", ""), []).append(source)
    lyric_tracks = [row for row in inventory if row["has_lyrics"]]
    output: list[dict[str, Any]] = []
    low_confidence: list[tuple[float, str]] = []
    for index, track in enumerate(lyric_tracks, 1):
        track_plain = compact_text(strip_lrc(track["lyrics"]))
        track_title = identity_text(track.get("title", ""))
        track_artist = identity_text(track.get("artist", ""))
        candidates: dict[tuple[str, str], dict[str, Any]] = {}
        for source in lyrics_index.get(track_plain, []):
            candidates[(source["source_set"], source["source_key"])] = source
        for source in path_index.get(track["relative_path"], []):
            candidates[(source["source_set"], source["source_key"])] = source
        if not candidates:
            for source in sources:
                title_ratio = SequenceMatcher(
                    None, track_title, source["_title_identity"], autojunk=False
                ).ratio()
                if title_ratio < 0.48:
                    continue
                artist_ratio = SequenceMatcher(
                    None, track_artist, source["_artist_identity"], autojunk=False
                ).ratio()
                duration_delta = abs(
                    float(track.get("duration") or 0) - float(source.get("duration") or 0)
                )
                if artist_ratio >= 0.42 or (title_ratio >= 0.88 and duration_delta <= 3):
                    candidates[(source["source_set"], source["source_key"])] = source
        ranked: list[tuple[float, dict[str, Any], list[str]]] = []
        for source in candidates.values():
            score, notes = source_match_score(track, source)
            if score >= 250:
                ranked.append((score, source, notes))
        ranked.sort(key=lambda item: item[0], reverse=True)
        if not ranked:
            output.append(
                {
                    "relative_path": track["relative_path"],
                    "metadata": {key: track.get(key, "") for key in ("title", "artist", "album", "duration")},
                    "current_lyrics": track["lyrics"],
                    "current_lyrics_sha256": track["lyrics_sha256"],
                    "status": "no_source",
                }
            )
            low_confidence.append((0, track["relative_path"]))
            continue
        best_score, source, notes = ranked[0]
        second_score = ranked[1][0] if len(ranked) > 1 else None
        confident = best_score >= args.minimum_score and (
            second_score is None or best_score - second_score >= args.minimum_margin
            or "lyrics_exact" in notes
        )
        output.append(
            {
                "relative_path": track["relative_path"],
                "metadata": {key: track.get(key, "") for key in ("title", "artist", "album", "duration")},
                "current_lyrics": track["lyrics"],
                "current_lyrics_sha256": track["lyrics_sha256"],
                "status": "matched" if confident else "review",
                "match_score": round(best_score, 3),
                "second_score": round(second_score, 3) if second_score is not None else None,
                "match_notes": notes,
                "source": {key: value for key, value in source.items() if not key.startswith("_")},
            }
        )
        if not confident:
            low_confidence.append((best_score, track["relative_path"]))
        if index % 100 == 0:
            print(f"matched {index}/{len(lyric_tracks)}", flush=True)

    # A fresh independent review found six tracks previously misclassified as
    # instrumental.  Their official Bandcamp pages supply exact full lyrics.
    inventory_by_path = {row["relative_path"]: row for row in inventory}
    existing_output_paths = {row["relative_path"] for row in output}
    for finding in read_jsonl(POSTROCK_FINDINGS_PATH):
        if finding.get("classification") != "lyrics_found":
            continue
        absolute = Path(finding["path"])
        relative = str(absolute.relative_to(MEDIA_ROOT))
        if relative in existing_output_paths:
            continue
        track = inventory_by_path.get(relative)
        if not track:
            raise RuntimeError(f"Bandcamp finding is absent from inventory: {relative}")
        cleaned = (finding.get("cleaned_lyrics") or "").strip()
        if not cleaned:
            raise RuntimeError(f"Bandcamp finding has no cleaned lyric: {relative}")
        output.append(
            {
                "relative_path": relative,
                "metadata": {
                    key: track.get(key, "") for key in ("title", "artist", "album", "duration")
                },
                "current_lyrics": cleaned,
                "current_lyrics_sha256": sha256_text(cleaned),
                "status": "matched",
                "match_score": 2000,
                "second_score": None,
                "match_notes": [
                    "official_bandcamp_exact_track",
                    "independent_no_lyrics_reaudit_found_lyrics",
                    finding.get("evidence", ""),
                ],
                "originally_empty": True,
                "source": {
                    "source_set": "postrock_reaudit_20260730",
                    "source_key": sha256_text(relative),
                    "source_path": relative,
                    "title": finding.get("matched_source_metadata", {}).get(
                        "title", track.get("title", "")
                    ),
                    "artist": finding.get("matched_source_metadata", {}).get(
                        "artist", track.get("artist", "")
                    ),
                    "album": finding.get("matched_source_metadata", {}).get(
                        "album", track.get("album", "")
                    ),
                    "duration": finding.get("source_duration_seconds")
                    or track.get("duration", 0),
                    "cleaned_lyrics": cleaned,
                    "raw_lyrics": finding.get("source_original_lyrics") or cleaned,
                    "selected": {
                        "source": "official_bandcamp",
                        "source_id": (finding.get("public_sources") or [""])[0],
                        "source_url": (finding.get("public_sources") or [""])[0],
                    },
                    "source_kind": "official_bandcamp",
                    "cleaning_notes": finding.get("cleaning_notes", []),
                },
            }
        )
        existing_output_paths.add(relative)
    output.sort(key=lambda row: row["relative_path"].casefold())
    write_jsonl(SOURCE_MAP_PATH, output)
    print(
        json.dumps(
            {
                "lyric_tracks": len(output),
                "statuses": Counter(row["status"] for row in output),
                "timed_raw_sources": sum(
                    bool(ANY_TIME_RE.search((row.get("source") or {}).get("raw_lyrics", "")))
                    for row in output
                ),
                "needs_timed_source": sum(
                    not bool(ANY_TIME_RE.search((row.get("source") or {}).get("raw_lyrics", "")))
                    for row in output
                ),
                "lowest": low_confidence[:20],
                "source_map": str(SOURCE_MAP_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    inventory = sub.add_parser("inventory")
    inventory.add_argument("--workers", type=int, default=12)
    inventory.set_defaults(func=command_inventory)

    match = sub.add_parser("match-sources")
    match.add_argument("--minimum-score", type=float, default=420)
    match.add_argument("--minimum-margin", type=float, default=35)
    match.set_defaults(func=command_match_sources)

    merge = sub.add_parser("merge-timing-sources")
    merge.set_defaults(func=command_merge_timing_sources)

    repair_text = sub.add_parser("repair-text")
    repair_text.set_defaults(func=command_repair_text)

    apply_skipped = sub.add_parser("apply-skipped-decisions")
    apply_skipped.set_defaults(func=command_apply_skipped_decisions)

    apply_direct = sub.add_parser("apply-direct-source-decisions")
    apply_direct.set_defaults(func=command_apply_direct_source_decisions)

    final_text = sub.add_parser("final-text-cleanups")
    final_text.set_defaults(func=command_final_text_cleanups)

    apply_review_texts = sub.add_parser("apply-review-texts")
    apply_review_texts.add_argument("--file", action="append", required=True)
    apply_review_texts.set_defaults(func=command_apply_review_texts)

    symbol_cleanups = sub.add_parser("build-final-symbol-cleanups")
    symbol_cleanups.set_defaults(func=command_build_final_symbol_cleanups)

    include_timed = sub.add_parser("include-preexisting-timed")
    include_timed.set_defaults(func=command_include_preexisting_timed)

    normalize_newlines = sub.add_parser("normalize-source-newlines")
    normalize_newlines.set_defaults(func=command_normalize_source_newlines)

    align = sub.add_parser("align")
    align.add_argument("--minimum-line-similarity", type=float, default=0.72)
    align.add_argument("--duration-slack", type=float, default=2.0)
    align.set_defaults(func=command_align)

    whisper_align = sub.add_parser("whisper-align")
    whisper_align.add_argument(
        "--status",
        action="append",
        choices=["needs_timed_source", "review", "ready"],
        default=None,
    )
    whisper_align.add_argument("--minimum-token-coverage", type=float, default=0.58)
    whisper_align.add_argument("--minimum-direct-line-ratio", type=float, default=0.82)
    whisper_align.add_argument("--minimum-mean-line-coverage", type=float, default=0.50)
    whisper_align.set_defaults(func=command_whisper_align)

    baseline = sub.add_parser("baseline")
    baseline.add_argument("--workers", type=int, default=6)
    baseline.set_defaults(func=command_baseline)

    backup_integrity = sub.add_parser("backup-integrity")
    backup_integrity.add_argument("--workers", type=int, default=4)
    backup_integrity.set_defaults(func=command_backup_integrity)

    assemble = sub.add_parser("assemble-final")
    assemble.set_defaults(func=command_assemble_final)

    apply_command = sub.add_parser("apply")
    apply_command.add_argument("--workers", type=int, default=6)
    apply_command.add_argument("--preflight-only", action="store_true")
    apply_command.set_defaults(func=command_apply)

    verify_final = sub.add_parser("verify-final")
    verify_final.add_argument("--workers", type=int, default=6)
    verify_final.set_defaults(func=command_verify_final)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "whisper-align" and not args.status:
        args.status = ["needs_timed_source", "review"]
    args.func(args)


if __name__ == "__main__":
    main()
