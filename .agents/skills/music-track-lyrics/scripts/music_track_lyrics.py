#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["mutagen>=1.47,<2"]
# ///
"""Atomic lyric operations and CLI subcommands for exactly one audio track.

The module never discovers libraries, work directories, backups, candidates,
or user decisions implicitly. Public operations are independently callable
functions and independently invocable CLI subcommands.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from itertools import pairwise
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile
from mutagen.id3 import USLT
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4

TIME_TAG_RE = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")
STRICT_LRC_RE = re.compile(
    r"^\[(?P<minute>\d{2,3}):(?P<second>\d{2})\.(?P<millisecond>\d{3})\](?P<text>.+)$"
)
META_TAG_RE = re.compile(r"^\[(?:ar|al|ti|by|offset|re|ve|length):", re.IGNORECASE)
SECTION_RE = re.compile(
    r"^\[(?:intro|verse|pre[- ]?chorus|chorus|bridge|hook|outro|interlude|instrumental)(?:\s+\d+)?\]$",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(
    r"^(?:纯音乐[，,、 ]*(?:请欣赏)?|此歌曲暂无文本歌词|暂无歌词|instrumental(?:\s+music)?|lyrics?\s+not\s+available)$",
    re.IGNORECASE,
)
URL_OR_PROMO_RE = re.compile(
    r"(?:https?://|www\.|QQ音乐|网易云|酷狗|虾米|VIP|付费|试听|下载|关注我们|公众号|歌词来源|仅供娱乐)",
    re.IGNORECASE,
)
CREDIT_RE = re.compile(
    r"^(?:作词|作詞|作曲|词曲|詞曲|编曲|編曲|制作人|製作人|录音|錄音|混音|母带|母帶|"
    r"演唱|主唱|和声|和聲|吉他|贝斯|貝斯|鼓|键盘|鍵盤|弦乐|弦樂|发行|發行|出品|"
    r"版权|版權|厂牌|廠牌|ISRC|OP|SP|producer|mixed by|mastered by|recorded by|"
    r"arranged by|lyrics by|music by)\s*[：:]",
    re.IGNORECASE,
)
ROLE_PREFIX_RE = re.compile(
    r"^(?:童|旁白|男|女|合|独|獨|齐|齊|众|眾|甲|乙)\s*[：:]\s*(?P<text>.+)$",
    re.IGNORECASE,
)
ROLE_ONLY_RE = re.compile(
    r"^(?:童|旁白|男|女|合|独|獨|齐|齊|众|眾|甲|乙)\s*[：:]?\s*$", re.IGNORECASE
)
PAREN_ROLE_RE = re.compile(r"^[（(]\s*[^：:()（）]{1,16}\s*[：:]\s*(?P<text>.+?)[）)]$")
TRANSCRIPTION_END_RE = re.compile(r"^--\s*end\s*--$", re.IGNORECASE)
NUMBER_MARKER_RE = re.compile(r"^(?:<\d+>|\d+[.)、])$")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def resolve_audio(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    audio = MutagenFile(path, easy=False)
    if not isinstance(audio, (MP4, MP3)):
        raise TypeError(f"only M4A/MP4 and MP3 are supported: {path}")
    return path


def resolve_backup_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_symlink():
        raise ValueError("backup must not be a symlink")
    return path.resolve()


def load_audio(path: Path) -> MP4 | MP3:
    audio = MutagenFile(path, easy=False)
    if not isinstance(audio, (MP4, MP3)):
        raise TypeError(f"only M4A/MP4 and MP3 are supported: {path}")
    return audio


def first(value: Any, default: str = "") -> str:
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else default
    return str(value) if value is not None else default


def _decode_freeform(value: Any) -> str:
    raw = value[0] if isinstance(value, (list, tuple)) and value else value
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return str(raw or "")


def metadata(audio: MP4 | MP3) -> dict[str, Any]:
    tags = audio.tags or {}
    if isinstance(audio, MP4):
        result = {
            "title": first(tags.get("©nam")),
            "artist": first(tags.get("©ART")),
            "album": first(tags.get("©alb")),
            "album_artist": first(tags.get("aART")),
            "track": first(tags.get("trkn")),
            "disc": first(tags.get("disk")),
            "isrc": "",
            "musicbrainz_track_id": "",
            "acoustid_id": "",
        }
        for key, value in tags.items():
            normalized = str(key).casefold().replace(" ", "")
            if normalized.startswith("----:com.apple.itunes:"):
                name = normalized.rsplit(":", 1)[-1]
                if name == "isrc":
                    result["isrc"] = _decode_freeform(value)
                elif name in {"musicbrainztrackid", "musicbrainz_track_id"}:
                    result["musicbrainz_track_id"] = _decode_freeform(value)
                elif name in {"acoustidid", "acoustid_id"}:
                    result["acoustid_id"] = _decode_freeform(value)
        return result

    def id3_text(frame_id: str) -> str:
        frames = tags.getall(frame_id) if audio.tags else []
        return first(getattr(frames[0], "text", "")) if frames else ""

    return {
        "title": id3_text("TIT2"),
        "artist": id3_text("TPE1"),
        "album": id3_text("TALB"),
        "album_artist": id3_text("TPE2"),
        "track": id3_text("TRCK"),
        "disc": id3_text("TPOS"),
        "isrc": id3_text("TSRC"),
        "musicbrainz_track_id": "",
        "acoustid_id": "",
    }


def embedded_lyrics(audio: MP4 | MP3) -> str:
    if isinstance(audio, MP4):
        return first((audio.tags or {}).get("©lyr"))
    frames = audio.tags.getall("USLT") if audio.tags else []
    return "\n\n".join(str(frame.text) for frame in frames if str(frame.text).strip())


def set_embedded_lyrics(path: Path, lyrics: str) -> None:
    audio = load_audio(path)
    if audio.tags is None:
        audio.add_tags()
    if isinstance(audio, MP4):
        if lyrics:
            audio.tags["©lyr"] = [lyrics]
        else:
            audio.tags.pop("©lyr", None)
        audio.save()
        return
    audio.tags.delall("USLT")
    if lyrics:
        audio.tags.add(USLT(encoding=3, lang="und", desc="", text=lyrics))
    audio.save(v2_version=4)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return text_sha256(raw)


def _canonical_tag_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    if isinstance(value, dict):
        return {
            str(key): _canonical_tag_value(item) for key, item in sorted(value.items())
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_tag_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def non_lyric_tag_snapshot(audio: MP4 | MP3) -> dict[str, Any]:
    if isinstance(audio, MP4):
        return {
            str(key): _canonical_tag_value(value)
            for key, value in sorted(
                (audio.tags or {}).items(), key=lambda item: str(item[0])
            )
            if str(key) != "©lyr"
        }
    result: dict[str, Any] = {}
    if not audio.tags:
        return result
    for frame in audio.tags.values():
        if getattr(frame, "FrameID", "") in {"USLT", "SYLT"}:
            continue
        key = str(
            getattr(frame, "HashKey", getattr(frame, "FrameID", type(frame).__name__))
        )
        if getattr(frame, "FrameID", "") == "APIC":
            raw = bytes(frame.data)
            result[key] = {
                "mime": frame.mime,
                "type": int(frame.type),
                "description": frame.desc,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        else:
            result[key] = str(frame)
    return result


def artwork_info(audio: MP4 | MP3) -> list[dict[str, Any]]:
    if isinstance(audio, MP4):
        return [
            {
                "bytes": len(bytes(item)),
                "sha256": hashlib.sha256(bytes(item)).hexdigest(),
            }
            for item in (audio.tags or {}).get("covr", [])
        ]
    return [
        {"bytes": len(frame.data), "sha256": hashlib.sha256(frame.data).hexdigest()}
        for frame in (audio.tags.getall("APIC") if audio.tags else [])
    ]


def _run_json(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "external command failed")
    return json.loads(result.stdout)


def audio_payload_sha256(path: Path, ffmpeg: str) -> str:
    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-c",
            "copy",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "ffmpeg audio hashing failed")
    match = re.search(r"SHA256=([0-9a-fA-F]+)", result.stdout)
    if not match:
        raise RuntimeError("ffmpeg did not return an audio hash")
    return match.group(1).lower()


def stream_snapshot(path: Path, ffprobe: str) -> dict[str, Any]:
    parsed = _run_json(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_type,codec_name,duration,channels,sample_rate,width,height:format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    return {
        "streams": parsed.get("streams", []),
        "format": parsed.get("format", {}),
    }


def track_snapshot(path: Path, ffmpeg: str, ffprobe: str) -> dict[str, Any]:
    audio = load_audio(path)
    lyrics = embedded_lyrics(audio)
    tags = non_lyric_tag_snapshot(audio)
    return {
        "schema": "music-lyrics/track-snapshot/v1",
        "audio_path": str(path),
        "format": "m4a" if isinstance(audio, MP4) else "mp3",
        "metadata": metadata(audio),
        "duration": round(float(getattr(audio.info, "length", 0.0)), 6),
        "lyrics": lyrics,
        "lyrics_sha256": text_sha256(lyrics),
        "whole_file_sha256": file_sha256(path),
        "size": path.stat().st_size,
        "non_lyric_tags": tags,
        "non_lyric_tag_sha256": canonical_json_sha256(tags),
        "artwork": artwork_info(audio),
        "audio_payload_sha256": audio_payload_sha256(path, ffmpeg),
        "streams": stream_snapshot(path, ffprobe),
        "captured_at": now_iso(),
    }


def load_json(path_text: str) -> Any:
    path = Path(path_text).expanduser().resolve()
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path_text: str) -> str:
    if path_text == "-":
        import sys

        return sys.stdin.read()
    return Path(path_text).expanduser().resolve().read_text(encoding="utf-8")


def read_lyrics_value(path_text: str, keys: tuple[str, ...], audio_path: Path) -> str:
    raw = read_text(path_text)
    try:
        value: Any = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    candidates: list[Any] = [value]
    if isinstance(value, dict):
        require_record_audio(value, audio_path)
        candidates.extend(
            item for item in (value.get("source"), value.get("proposal")) if item
        )
    for candidate in candidates[1:]:
        if isinstance(candidate, dict) and "audio_path" in candidate:
            require_record_audio(candidate, audio_path)
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for key in keys:
            found = candidate.get(key)
            if isinstance(found, str):
                return found
    raise ValueError(f"JSON input has none of the requested lyric fields: {keys}")


def write_json(value: Any, output: str | None) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output:
        path = Path(output).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(path)
    else:
        print(rendered, end="")


def write_text(value: str, output: str) -> None:
    path = Path(output).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def artist_atoms(value: str, aliases: dict[str, str]) -> set[str]:
    parts = re.split(
        r"\s*(?:,|，|、|&|／|/|;|；|\bfeat(?:uring)?\.?\b|\bft\.?\b|\band\b)\s*",
        value,
        flags=re.IGNORECASE,
    )
    result: set[str] = set()
    normalized_aliases = {
        normalize(key): normalize(item) for key, item in aliases.items()
    }
    for part in parts:
        item = normalize(part)
        if item:
            result.add(normalized_aliases.get(item, item))
    return result


def clean_lyrics(
    raw: str, title: str, artist: str, heading_lines: set[int] | None = None
) -> tuple[str, list[dict[str, Any]]]:
    transformations: list[dict[str, Any]] = []
    output: list[str] = []
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    for line_number, raw_line in enumerate(normalized.split("\n"), 1):
        original = raw_line
        timestamp_count = len(TIME_TAG_RE.findall(raw_line))
        line = TIME_TAG_RE.sub("", raw_line).strip()
        if timestamp_count:
            transformations.append(
                {
                    "line": line_number,
                    "category": "timestamp",
                    "original": original,
                    "removed_count": timestamp_count,
                }
            )
        if not line:
            output.append("")
            continue
        category = ""
        if META_TAG_RE.match(line):
            category = "lrc_metadata"
        elif SECTION_RE.fullmatch(line):
            category = "section_label"
        elif CREDIT_RE.match(line):
            category = "credit"
        elif URL_OR_PROMO_RE.search(line):
            category = "promotion_or_source_notice"
        elif PLACEHOLDER_RE.fullmatch(line):
            category = "placeholder"
        elif TRANSCRIPTION_END_RE.fullmatch(line):
            category = "transcription_terminator"
        elif NUMBER_MARKER_RE.fullmatch(line):
            category = "number_marker"
        elif ROLE_ONLY_RE.fullmatch(line):
            category = "empty_role"
        elif line_number in (heading_lines or ()) and normalize(line) in {
            normalize(title),
            normalize(title + artist),
            normalize(artist + title),
        }:
            category = "title_residue"
        if category:
            transformations.append(
                {"line": line_number, "category": category, "original": original}
            )
            output.append("")
            continue
        role_match = ROLE_PREFIX_RE.match(line) or PAREN_ROLE_RE.match(line)
        if role_match:
            replacement = role_match.group("text").strip()
            transformations.append(
                {
                    "line": line_number,
                    "category": "role_prefix",
                    "original": original,
                    "replacement": replacement,
                }
            )
            line = replacement
        output.append(unicodedata.normalize("NFC", line))

    collapsed: list[str] = []
    for line in output:
        if line or (collapsed and collapsed[-1]):
            collapsed.append(line)
    while collapsed and not collapsed[-1]:
        collapsed.pop()
    return "\n".join(collapsed), transformations


def residual_flags(lyrics: str) -> list[str]:
    flags: set[str] = set()
    for line in lyrics.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if TIME_TAG_RE.search(stripped):
            flags.add("timestamp")
        if CREDIT_RE.match(stripped):
            flags.add("credit")
        if URL_OR_PROMO_RE.search(stripped):
            flags.add("promotion_or_source_notice")
        if PLACEHOLDER_RE.fullmatch(stripped):
            flags.add("placeholder")
        if SECTION_RE.fullmatch(stripped):
            flags.add("section_label")
    return sorted(flags)


def segment_lyrics(
    lyrics: str,
    gap_seconds: float,
    explicit_breaks: set[int],
) -> tuple[str, list[dict[str, Any]]]:
    normalized = lyrics.replace("\r\n", "\n").replace("\r", "\n").strip()
    output: list[str] = []
    changes: list[dict[str, Any]] = []
    previous_time: float | None = None
    lyric_index = 0
    for raw_line in normalized.split("\n"):
        if not raw_line.strip():
            if output and output[-1] != "":
                output.append("")
            previous_time = None
            continue
        lyric_index += 1
        matches = list(TIME_TAG_RE.finditer(raw_line))
        current_time = _time_from_match(matches[0]) if matches else None
        reason = ""
        if lyric_index in explicit_breaks:
            reason = "explicit_break"
        elif (
            current_time is not None
            and previous_time is not None
            and current_time - previous_time >= gap_seconds
        ):
            reason = f"timestamp_gap:{current_time - previous_time:.3f}"
        if reason and output and output[-1] != "":
            output.append("")
            changes.append({"before_lyric_line": lyric_index, "reason": reason})
        output.append(raw_line.strip())
        previous_time = current_time
    while output and output[-1] == "":
        output.pop()
    return "\n".join(output), changes


@dataclass(frozen=True)
class LrcEvent:
    seconds: float
    text: str
    source_line: int


def _time_from_match(match: re.Match[str]) -> float:
    fraction_text = match.group(3) or "0"
    fraction = int(fraction_text) / (10 ** len(fraction_text))
    return int(match.group(1)) * 60 + int(match.group(2)) + fraction


def parse_lrc(value: str) -> list[LrcEvent]:
    events: list[LrcEvent] = []
    for line_number, raw_line in enumerate(
        value.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1
    ):
        matches = list(TIME_TAG_RE.finditer(raw_line))
        if not matches:
            continue
        text = TIME_TAG_RE.sub("", raw_line).strip()
        if not text or META_TAG_RE.match(text):
            continue
        for match in matches:
            events.append(LrcEvent(_time_from_match(match), text, line_number))
    return sorted(events, key=lambda event: (event.seconds, event.source_line))


def strip_lrc(value: str) -> str:
    output: list[str] = []
    for raw_line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if META_TAG_RE.match(raw_line.strip()):
            continue
        output.append(TIME_TAG_RE.sub("", raw_line).rstrip())
    while output and not output[0].strip():
        output.pop(0)
    while output and not output[-1].strip():
        output.pop()
    return "\n".join(output)


def line_similarity(left: str, right: str) -> float:
    normalized_left = normalize(left)
    normalized_right = normalize(right)
    if not normalized_left or not normalized_right:
        return 0.0
    if normalized_left == normalized_right:
        return 1.0
    shorter, longer = sorted((normalized_left, normalized_right), key=len)
    containment = len(shorter) / len(longer) if shorter in longer else 0.0
    ratio = SequenceMatcher(
        None, normalized_left, normalized_right, autojunk=False
    ).ratio()
    if containment >= 0.58:
        ratio = max(ratio, 0.82 + 0.16 * containment)
    return ratio


@dataclass
class Alignment:
    times: list[float]
    kinds: list[str]
    similarities: list[float]
    source_indices: list[list[int]]
    skipped_source_indices: list[int]


def align_lines(
    target_lines: list[str],
    events: list[LrcEvent],
    split_window_seconds: float,
) -> Alignment:
    target_count, source_count = len(target_lines), len(events)
    negative = -(10**30)
    scores = [[negative] * (source_count + 1) for _ in range(target_count + 1)]
    back: list[list[tuple[int, int, str, float] | None]] = [
        [None] * (source_count + 1) for _ in range(target_count + 1)
    ]
    scores[0][0] = 0.0

    def update(
        new_target: int,
        new_source: int,
        score: float,
        old_target: int,
        old_source: int,
        operation: str,
        similarity: float = 0.0,
    ) -> None:
        if score > scores[new_target][new_source]:
            scores[new_target][new_source] = score
            back[new_target][new_source] = (
                old_target,
                old_source,
                operation,
                similarity,
            )

    for target_index in range(target_count + 1):
        for source_index in range(source_count + 1):
            base = scores[target_index][source_index]
            if base <= negative / 2:
                continue
            if source_index < source_count:
                update(
                    target_index,
                    source_index + 1,
                    base - 0.055,
                    target_index,
                    source_index,
                    "skip_source",
                )
            if target_index < target_count:
                update(
                    target_index + 1,
                    source_index,
                    base - 1.10,
                    target_index,
                    source_index,
                    "skip_target",
                )
            if target_index < target_count and source_index < source_count:
                similarity = line_similarity(
                    target_lines[target_index], events[source_index].text
                )
                if similarity >= 0.28:
                    update(
                        target_index + 1,
                        source_index + 1,
                        base + 2.8 * similarity - 0.9,
                        target_index,
                        source_index,
                        "match_1_1",
                        similarity,
                    )
            if target_index < target_count and source_index + 1 < source_count:
                similarity = line_similarity(
                    target_lines[target_index],
                    events[source_index].text + events[source_index + 1].text,
                )
                if similarity >= 0.42:
                    update(
                        target_index + 1,
                        source_index + 2,
                        base + 2.75 * similarity - 0.98,
                        target_index,
                        source_index,
                        "match_1_2",
                        similarity,
                    )
            if target_index + 1 < target_count and source_index < source_count:
                similarity = line_similarity(
                    target_lines[target_index] + target_lines[target_index + 1],
                    events[source_index].text,
                )
                if similarity >= 0.42:
                    update(
                        target_index + 2,
                        source_index + 1,
                        base + 2.75 * similarity - 0.98,
                        target_index,
                        source_index,
                        "match_2_1",
                        similarity,
                    )

    operations: list[tuple[int, int, int, int, str, float]] = []
    target_index, source_index = target_count, source_count
    while target_index or source_index:
        previous = back[target_index][source_index]
        if previous is None:
            raise RuntimeError(
                f"lyric alignment failed at {target_index},{source_index}"
            )
        old_target, old_source, operation, similarity = previous
        operations.append(
            (
                old_target,
                old_source,
                target_index,
                source_index,
                operation,
                similarity,
            )
        )
        target_index, source_index = old_target, old_source
    operations.reverse()

    raw_times: list[float | None] = [None] * target_count
    kinds = ["unmatched"] * target_count
    similarities = [0.0] * target_count
    source_indices: list[list[int]] = [[] for _ in range(target_count)]
    skipped_sources: list[int] = []
    for old_target, old_source, _, _, operation, similarity in operations:
        if operation == "skip_source":
            skipped_sources.append(old_source)
        elif operation == "match_1_1":
            raw_times[old_target] = events[old_source].seconds
            kinds[old_target] = operation
            similarities[old_target] = similarity
            source_indices[old_target] = [old_source]
        elif operation == "match_1_2":
            raw_times[old_target] = events[old_source].seconds
            kinds[old_target] = operation
            similarities[old_target] = similarity
            source_indices[old_target] = [old_source, old_source + 1]
        elif operation == "match_2_1":
            start = events[old_source].seconds
            following = (
                events[old_source + 1].seconds
                if old_source + 1 < source_count
                else start + split_window_seconds
            )
            available = min(split_window_seconds, max(0.4, following - start))
            left_length = max(1, len(normalize(target_lines[old_target])))
            right_length = max(1, len(normalize(target_lines[old_target + 1])))
            split = start + available * left_length / (left_length + right_length)
            raw_times[old_target] = start
            raw_times[old_target + 1] = split
            kinds[old_target] = operation
            kinds[old_target + 1] = "match_2_1_interpolated"
            similarities[old_target] = similarity
            similarities[old_target + 1] = similarity
            source_indices[old_target] = [old_source]
            source_indices[old_target + 1] = [old_source]

    matched = [index for index, value in enumerate(raw_times) if value is not None]
    for index, value in enumerate(raw_times):
        if value is not None:
            continue
        before = max((item for item in matched if item < index), default=None)
        after = min((item for item in matched if item > index), default=None)
        if before is not None and after is not None:
            fraction = (index - before) / (after - before)
            raw_times[index] = (
                float(raw_times[before])
                + (float(raw_times[after]) - float(raw_times[before])) * fraction
            )
        elif before is not None:
            raw_times[index] = float(raw_times[before]) + 2.0 * (index - before)
        elif after is not None:
            raw_times[index] = max(0.0, float(raw_times[after]) - 2.0 * (after - index))
        else:
            raw_times[index] = 2.0 * index
        kinds[index] = "unmatched_interpolated"

    times = [float(value) for value in raw_times]
    last = -0.001
    for index, value in enumerate(times):
        if value <= last:
            times[index] = last + 0.001
            kinds[index] += "+monotonic_adjusted"
        last = times[index]
    return Alignment(times, kinds, similarities, source_indices, skipped_sources)


def format_lrc_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    minute, remainder = divmod(milliseconds, 60_000)
    second, millisecond = divmod(remainder, 1000)
    return f"[{minute:02d}:{second:02d}.{millisecond:03d}]"


def render_timed_lyrics(plain_lyrics: str, times: Iterable[float]) -> str:
    iterator = iter(times)
    output: list[str] = []
    for raw_line in plain_lyrics.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not raw_line.strip():
            if output and output[-1] != "":
                output.append("")
            continue
        output.append(format_lrc_time(next(iterator)) + raw_line.strip())
    try:
        next(iterator)
    except StopIteration:
        pass
    else:
        raise ValueError("more timestamps than lyric lines")
    while output and output[-1] == "":
        output.pop()
    return "\n".join(output)


def strict_lrc_times(value: str) -> list[float]:
    times: list[float] = []
    for line_number, raw_line in enumerate(
        value.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1
    ):
        if not raw_line:
            continue
        match = STRICT_LRC_RE.fullmatch(raw_line)
        if not match:
            raise ValueError(f"line {line_number} is not strict LRC: {raw_line!r}")
        second = int(match.group("second"))
        if second >= 60:
            raise ValueError(f"line {line_number} has an invalid second value")
        times.append(
            int(match.group("minute")) * 60
            + second
            + int(match.group("millisecond")) / 1000
        )
    return times


def validate_timed_lyrics(
    timed_lyrics: str, plain_lyrics: str, duration: float
) -> dict[str, Any]:
    issues: list[str] = []
    try:
        times = strict_lrc_times(timed_lyrics.strip())
    except ValueError as error:
        return {"valid": False, "issues": [str(error)]}
    plain = plain_lyrics.replace("\r\n", "\n").replace("\r", "\n").strip()
    stripped = strip_lrc(timed_lyrics).strip()
    plain_line_count = sum(bool(line.strip()) for line in plain.splitlines())
    if len(times) != plain_line_count:
        issues.append(f"line_count:{len(times)}!={plain_line_count}")
    if stripped != plain:
        issues.append("stripped_text_mismatch")
    if any(right <= left for left, right in pairwise(times)):
        issues.append("timestamps_not_strictly_increasing")
    if times and times[-1] > duration:
        issues.append(f"timestamp_after_duration:{times[-1]:.3f}>{duration:.3f}")
    return {
        "valid": not issues,
        "issues": issues,
        "line_count": len(times),
        "first_timestamp": round(times[0], 3) if times else None,
        "last_timestamp": round(times[-1], 3) if times else None,
        "strictly_increasing": not any(
            right <= left for left, right in pairwise(times)
        ),
        "within_duration": not times or times[-1] <= duration,
        "stripped_text_sha256": text_sha256(stripped),
    }


def proposal_lyrics(record: dict[str, Any]) -> str:
    value = record.get("lyrics")
    if not isinstance(value, str):
        raise TypeError("proposal must contain a string 'lyrics' field")
    return value


def require_record_audio(record: dict[str, Any], audio_path: Path) -> None:
    value = record.get("audio_path")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("record must contain an audio_path")
    recorded = Path(value).expanduser().resolve()
    if recorded != audio_path.expanduser().resolve():
        raise ValueError(f"record belongs to a different audio file: {recorded}")


# Atomic operations


def inspect_track(audio_path: Path, ffmpeg: str, ffprobe: str) -> dict[str, Any]:
    """Return a complete immutable-state snapshot for one track."""

    return track_snapshot(audio_path, ffmpeg, ffprobe)


def _request_json(
    endpoint: str,
    params: dict[str, object],
    timeout: float,
    user_agent: str,
) -> tuple[Any, str]:
    separator = "&" if "?" in endpoint else "?"
    url = endpoint + separator + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace")), url


def search_source(
    audio_path: Path,
    provider: str,
    endpoint: str,
    query: str | None,
    limit: int,
    timeout: float,
    user_agent: str,
) -> dict[str, Any]:
    """Search one explicit provider endpoint for one track."""

    local = metadata(load_audio(audio_path))
    resolved_query = query or " ".join(
        item for item in (local.get("title", ""), local.get("artist", "")) if item
    )
    if provider == "lrclib":
        payload, requested_url = _request_json(
            endpoint,
            {
                "track_name": local.get("title", ""),
                "artist_name": local.get("artist", ""),
            },
            timeout,
            user_agent,
        )
        items = payload if isinstance(payload, list) else []
        candidates = [
            {
                "provider": "lrclib",
                "source_id": str(item.get("id", "")),
                "title": str(item.get("trackName", "")),
                "artists": [str(item.get("artistName", ""))],
                "album": str(item.get("albumName", "")),
                "duration": float(item.get("duration") or 0.0),
                "instrumental": bool(item.get("instrumental")),
                "plain_lyrics": item.get("plainLyrics") or "",
                "synchronized_lyrics": item.get("syncedLyrics") or "",
            }
            for item in items[:limit]
        ]
    elif provider == "netease":
        payload, requested_url = _request_json(
            endpoint,
            {"s": resolved_query, "type": 1, "limit": limit},
            timeout,
            user_agent,
        )
        items = (payload.get("result") or {}).get("songs") or []
        candidates = []
        for item in items[:limit]:
            album = item.get("album") or item.get("al") or {}
            artists = item.get("artists") or item.get("ar") or []
            duration_ms = item.get("duration") or item.get("dt") or 0
            candidates.append(
                {
                    "provider": "netease",
                    "source_id": str(item.get("id", "")),
                    "title": str(item.get("name", "")),
                    "artists": [str(artist.get("name", "")) for artist in artists],
                    "album": str(album.get("name", "")),
                    "duration": float(duration_ms) / 1000.0 if duration_ms else 0.0,
                    "instrumental": None,
                    "plain_lyrics": "",
                    "synchronized_lyrics": "",
                }
            )
    else:
        raise ValueError(f"unsupported provider: {provider}")
    return {
        "schema": "music-lyrics/source-search/v1",
        "audio_path": str(audio_path),
        "local_metadata": local,
        "provider": provider,
        "endpoint": endpoint,
        "requested_url": requested_url,
        "query": resolved_query,
        "candidates": candidates,
        "searched_at": now_iso(),
    }


def _fetch_json(url: str, timeout: float, user_agent: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def fetch_source(
    audio_path: Path,
    search_record: dict[str, Any],
    candidate_index: int,
    endpoint: str,
    timeout: float,
    user_agent: str,
) -> dict[str, Any]:
    """Fetch one explicitly selected candidate for one track."""

    require_record_audio(search_record, audio_path)
    candidate = dict(search_record["candidates"][candidate_index])
    provider = candidate["provider"]
    source_id = candidate["source_id"]
    if provider == "lrclib":
        encoded_id = urllib.parse.quote(str(source_id), safe="")
        url = (
            endpoint.replace("{id}", encoded_id)
            if "{id}" in endpoint
            else endpoint.rstrip("/") + "/" + encoded_id
        )
        payload = _fetch_json(url, timeout, user_agent)
        candidate.update(
            {
                "title": str(payload.get("trackName", candidate.get("title", ""))),
                "artists": [str(payload.get("artistName", ""))],
                "album": str(payload.get("albumName", candidate.get("album", ""))),
                "duration": float(
                    payload.get("duration") or candidate.get("duration") or 0
                ),
                "instrumental": bool(payload.get("instrumental")),
                "plain_lyrics": payload.get("plainLyrics") or "",
                "synchronized_lyrics": payload.get("syncedLyrics") or "",
            }
        )
    elif provider == "netease":
        separator = "&" if "?" in endpoint else "?"
        url = (
            endpoint
            + separator
            + urllib.parse.urlencode(
                {"id": source_id, "lv": -1, "kv": -1, "tv": -1, "yv": -1}
            )
        )
        payload = _fetch_json(url, timeout, user_agent)
        candidate.update(
            {
                "plain_lyrics": (payload.get("lrc") or {}).get("lyric") or "",
                "synchronized_lyrics": (payload.get("lrc") or {}).get("lyric") or "",
                "word_synchronized_lyrics": (payload.get("yrc") or {}).get("lyric")
                or "",
            }
        )
    else:
        raise ValueError(f"unsupported provider in candidate: {provider}")
    return {
        "schema": "music-lyrics/source-fetch/v1",
        "audio_path": str(audio_path),
        "source": candidate,
        "endpoint": endpoint,
        "requested_url": url,
        "fetched_at": now_iso(),
    }


def match_source(
    audio_path: Path,
    source_record: dict[str, Any],
    aliases: dict[str, str],
    duration_tolerance: float,
) -> dict[str, Any]:
    """Compare one fetched source with one track."""

    require_record_audio(source_record, audio_path)
    source = source_record["source"]
    local_audio = load_audio(audio_path)
    local = metadata(local_audio)
    source_artists = [str(item) for item in source.get("artists") or []]
    local_artists = artist_atoms(local.get("artist", ""), aliases)
    remote_artists = artist_atoms(" / ".join(source_artists), aliases)
    title_match = bool(normalize(local.get("title", ""))) and normalize(
        local.get("title", "")
    ) == normalize(source.get("title", ""))
    artist_match = bool(local_artists & remote_artists)
    album_match = bool(normalize(local.get("album", ""))) and normalize(
        local.get("album", "")
    ) == normalize(source.get("album", ""))
    local_duration = float(getattr(local_audio.info, "length", 0.0))
    source_duration = float(source.get("duration") or 0.0)
    duration_difference = (
        abs(local_duration - source_duration) if source_duration else None
    )
    duration_match = (
        duration_difference is not None and duration_difference <= duration_tolerance
    )
    checks = {
        "title": title_match,
        "artist": artist_match,
        "duration": duration_match,
        "not_instrumental": source.get("instrumental") is not True,
    }
    differences = []
    if not title_match:
        differences.append(
            f"title:{local.get('title', '')!r}!={source.get('title', '')!r}"
        )
    if not artist_match:
        differences.append(
            f"artist:{local.get('artist', '')!r}!={' / '.join(source_artists)!r}"
        )
    if not album_match:
        differences.append(
            f"album:{local.get('album', '')!r}!={source.get('album', '')!r}"
        )
    if not duration_match:
        differences.append(f"duration_difference:{duration_difference!r}")
    return {
        "schema": "music-lyrics/source-match/v1",
        "audio_path": str(audio_path),
        "source_record_sha256": canonical_json_sha256(source_record),
        "local_metadata": {**local, "duration": local_duration},
        "source_metadata": {
            key: source.get(key)
            for key in (
                "provider",
                "source_id",
                "title",
                "artists",
                "album",
                "duration",
                "instrumental",
            )
        },
        "checks": checks,
        "album_match": album_match,
        "accepted": all(checks.values()),
        "differences": differences,
        "duration_difference": duration_difference,
        "duration_tolerance": duration_tolerance,
        "matched_at": now_iso(),
    }


def clean_track_lyrics(
    audio_path: Path, raw_lyrics: str, heading_lines: set[int] | None = None
) -> dict[str, Any]:
    """Clean one lyric text using metadata from one track."""

    local = metadata(load_audio(audio_path))
    cleaned, transformations = clean_lyrics(
        raw_lyrics, local.get("title", ""), local.get("artist", ""), heading_lines
    )
    return {
        "schema": "music-lyrics/cleaned-proposal/v1",
        "audio_path": str(audio_path),
        "lyrics": cleaned,
        "lyrics_sha256": text_sha256(cleaned),
        "input_lyrics_sha256": text_sha256(raw_lyrics),
        "transformations": transformations,
        "residual_flags": residual_flags(cleaned),
        "created_at": now_iso(),
    }


def segment_track_lyrics(
    audio_path: Path,
    lyrics: str,
    gap_seconds: float,
    explicit_breaks: set[int],
) -> dict[str, Any]:
    """Add reviewed paragraph boundaries to one lyric text."""

    segmented, changes = segment_lyrics(lyrics, gap_seconds, explicit_breaks)
    return {
        "schema": "music-lyrics/segmented-proposal/v1",
        "audio_path": str(audio_path),
        "lyrics": segmented,
        "lyrics_sha256": text_sha256(segmented),
        "input_lyrics_sha256": text_sha256(lyrics),
        "paragraph_changes": changes,
        "created_at": now_iso(),
    }


def align_track_lyrics(
    audio_path: Path,
    plain_lyrics: str,
    timed_source: str,
    minimum_similarity: float,
    split_window_seconds: float,
    overrides: dict[str, float],
) -> dict[str, Any]:
    """Align one track's plain lyrics to one existing synchronized source."""

    plain = strip_lrc(plain_lyrics).strip()
    events = parse_lrc(timed_source)
    if not events:
        raise ValueError("timed source contains no lyric events")
    target_lines = [line.strip() for line in plain.splitlines() if line.strip()]
    if not target_lines:
        raise ValueError("plain lyric input is empty")
    alignment = align_lines(target_lines, events, split_window_seconds)
    applied_overrides = []
    for raw_index, raw_seconds in overrides.items():
        index = int(raw_index)
        old_seconds = alignment.times[index]
        alignment.times[index] = float(raw_seconds)
        alignment.kinds[index] = "explicit_override"
        applied_overrides.append(
            {
                "line_index": index,
                "old_seconds": old_seconds,
                "new_seconds": float(raw_seconds),
            }
        )
    rendered = render_timed_lyrics(plain, alignment.times)
    duration = float(getattr(load_audio(audio_path).info, "length", 0.0))
    validation = validate_timed_lyrics(rendered, plain, duration)
    low_similarity = [
        {
            "line_index": index,
            "text": target_lines[index],
            "similarity": similarity,
            "source_indices": alignment.source_indices[index],
        }
        for index, similarity in enumerate(alignment.similarities)
        if similarity < minimum_similarity
    ]
    approximated = [
        {"line_index": index, "text": target_lines[index], "kind": kind}
        for index, kind in enumerate(alignment.kinds)
        if "interpolated" in kind or "monotonic_adjusted" in kind
    ]
    status = (
        "ready"
        if validation.get("valid") and not low_similarity and not approximated
        else "review"
    )
    return {
        "schema": "music-lyrics/timed-proposal/v1",
        "audio_path": str(audio_path),
        "lyrics": rendered,
        "lyrics_sha256": text_sha256(rendered),
        "plain_lyrics": plain,
        "plain_lyrics_sha256": text_sha256(plain),
        "status": status,
        "source_event_count": len(events),
        "target_line_count": len(target_lines),
        "minimum_similarity": min(alignment.similarities),
        "mean_similarity": sum(alignment.similarities) / len(alignment.similarities),
        "minimum_required_similarity": minimum_similarity,
        "alignment_kinds": dict(Counter(alignment.kinds)),
        "low_similarity_lines": low_similarity,
        "approximated_lines": approximated,
        "skipped_source_indices": alignment.skipped_source_indices,
        "explicit_overrides": applied_overrides,
        "validation": validation,
        "created_at": now_iso(),
    }


def classify_track(
    audio_path: Path,
    lyrics: str | None,
    source_record: dict[str, Any] | None,
    instrumental_evidence: list[str],
) -> dict[str, Any]:
    """Classify one track without inferring instrumental status from silence."""

    selected_lyrics = (
        lyrics if lyrics is not None else embedded_lyrics(load_audio(audio_path))
    )
    body_lines = [
        line.strip()
        for line in strip_lrc(selected_lyrics).splitlines()
        if line.strip() and not PLACEHOLDER_RE.fullmatch(line.strip())
    ]
    source_instrumental = False
    if source_record:
        require_record_audio(source_record, audio_path)
        source = source_record.get("source", source_record)
        source_instrumental = source.get("instrumental") is True
    if body_lines:
        classification = "lyrical"
        reason = "lyric body is present"
    elif source_instrumental or instrumental_evidence:
        classification = "instrumental"
        reason = "explicit instrumental evidence is present"
    else:
        classification = "unresolved"
        reason = "no lyric body and no affirmative instrumental evidence"
    return {
        "schema": "music-lyrics/classification/v1",
        "audio_path": str(audio_path),
        "classification": classification,
        "reason": reason,
        "lyric_line_count": len(body_lines),
        "source_marked_instrumental": source_instrumental,
        "instrumental_evidence": instrumental_evidence,
        "classified_at": now_iso(),
    }


def approve_change(
    audio_path: Path,
    proposal: dict[str, Any],
    match_record: dict[str, Any] | None,
    decision: str,
    reviewer: str,
    reason: str,
    manual_match_override: bool,
) -> dict[str, Any]:
    """Bind one explicit decision to one proposal and current track state."""

    require_record_audio(proposal, audio_path)
    lyrics = proposal_lyrics(proposal)
    if match_record:
        require_record_audio(match_record, audio_path)
        if (
            decision == "accept"
            and not match_record.get("accepted")
            and not manual_match_override
        ):
            raise ValueError(
                "the source match is not accepted; explicit override is required"
            )
    current_lyrics = embedded_lyrics(load_audio(audio_path))
    return {
        "schema": "music-lyrics/change-approval/v1",
        "audio_path": str(audio_path),
        "decision": decision,
        "reviewer": reviewer,
        "reason": reason,
        "manual_match_override": manual_match_override,
        "proposal_sha256": canonical_json_sha256(proposal),
        "proposal_lyrics_sha256": text_sha256(lyrics),
        "match_record_sha256": (
            canonical_json_sha256(match_record) if match_record else None
        ),
        "current_whole_file_sha256": file_sha256(audio_path),
        "current_lyrics_sha256": text_sha256(current_lyrics),
        "reviewed_at": now_iso(),
    }


def backup_track(audio_path: Path, backup_path: Path) -> dict[str, Any]:
    """Create one independent, byte-identical backup for one track."""

    backup_path = resolve_backup_path(backup_path)
    if backup_path == audio_path:
        raise ValueError("backup path must differ from the audio path")
    if backup_path.exists() or backup_path.is_symlink():
        raise FileExistsError(backup_path)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(audio_path, backup_path)
    checks = {
        "present": backup_path.is_file(),
        "not_symlink": not backup_path.is_symlink(),
        "independent_inode": not os.path.samestat(
            os.stat(audio_path), os.stat(backup_path)
        ),
        "size_exact": audio_path.stat().st_size == backup_path.stat().st_size,
        "whole_file_sha256_exact": file_sha256(audio_path) == file_sha256(backup_path),
    }
    if not all(checks.values()):
        backup_path.unlink(missing_ok=True)
        raise RuntimeError(f"backup verification failed: {checks}")
    return {
        "schema": "music-lyrics/track-backup/v1",
        "audio_path": str(audio_path),
        "backup_path": str(backup_path),
        "whole_file_sha256": file_sha256(backup_path),
        "size": backup_path.stat().st_size,
        "checks": checks,
        "created_at": now_iso(),
    }


def write_track_lyrics(
    audio_path: Path,
    proposal: dict[str, Any],
    approval: dict[str, Any],
    backup_path: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    """Write one approved proposal, verifying the result or restoring the backup."""

    require_record_audio(proposal, audio_path)
    require_record_audio(approval, audio_path)
    lyrics = proposal_lyrics(proposal)
    if approval.get("decision") != "accept":
        raise ValueError("approval decision is not accept")
    if approval.get("proposal_sha256") != canonical_json_sha256(proposal):
        raise ValueError("approval does not bind this proposal")
    if approval.get("proposal_lyrics_sha256") != text_sha256(lyrics):
        raise ValueError("approved lyric hash differs from the proposal")
    backup_path = resolve_backup_path(backup_path)
    resolve_audio(str(backup_path))
    if os.path.samestat(os.stat(audio_path), os.stat(backup_path)):
        raise ValueError("backup must not be a hard link to the audio file")
    baseline = track_snapshot(audio_path, ffmpeg, ffprobe)
    if baseline["whole_file_sha256"] != file_sha256(backup_path):
        raise ValueError("backup is not byte-identical to the current audio file")
    if approval.get("current_whole_file_sha256") != baseline["whole_file_sha256"]:
        raise ValueError("audio file changed after approval")
    if approval.get("current_lyrics_sha256") != baseline["lyrics_sha256"]:
        raise ValueError("embedded lyrics changed after approval")
    if TIME_TAG_RE.search(lyrics):
        plain = str(proposal.get("plain_lyrics") or strip_lrc(lyrics)).strip()
        validation = validate_timed_lyrics(lyrics, plain, float(baseline["duration"]))
        if not validation.get("valid"):
            raise ValueError(f"timed proposal is invalid: {validation.get('issues')}")
    try:
        set_embedded_lyrics(audio_path, lyrics)
        after = track_snapshot(audio_path, ffmpeg, ffprobe)
        verification = _verification_result(
            audio_path, baseline, proposal, after, backup_path
        )
        if not verification["passed"]:
            raise RuntimeError(
                f"post-write verification failed: {verification['checks']}"
            )
    except Exception:
        shutil.copy2(backup_path, audio_path)
        raise
    return {
        "schema": "music-lyrics/write-result/v1",
        "audio_path": str(audio_path),
        "backup_path": str(backup_path),
        "proposal_sha256": canonical_json_sha256(proposal),
        "approval_sha256": canonical_json_sha256(approval),
        "lyrics_sha256": text_sha256(lyrics),
        "timed_validation": verification["timed_validation"],
        "residual_flags": verification["residual_flags"],
        "checks": verification["checks"],
        "passed": verification["passed"],
        "baseline": baseline,
        "after": after,
        "written_at": now_iso(),
    }


def _verification_result(
    audio_path: Path,
    baseline: dict[str, Any],
    proposal: dict[str, Any],
    current: dict[str, Any],
    backup_path: Path | None,
) -> dict[str, Any]:
    """Apply the same checks to a writer snapshot or an independent snapshot."""

    require_record_audio(baseline, audio_path)
    require_record_audio(proposal, audio_path)
    expected = proposal_lyrics(proposal)
    checks = {
        "lyrics_exact": current["lyrics"] == expected,
        "non_lyric_metadata_unchanged": current["non_lyric_tag_sha256"]
        == baseline["non_lyric_tag_sha256"],
        "artwork_unchanged": current["artwork"] == baseline["artwork"],
        "audio_payload_unchanged": current["audio_payload_sha256"]
        == baseline["audio_payload_sha256"],
        "streams_unchanged": current["streams"] == baseline["streams"],
        "format_unchanged": current["format"] == baseline["format"],
    }
    if backup_path:
        backup_path = resolve_backup_path(backup_path)
        checks["backup_independent"] = not os.path.samestat(
            os.stat(audio_path), os.stat(backup_path)
        )
        checks["backup_exact_original"] = (
            file_sha256(backup_path) == baseline["whole_file_sha256"]
        )
    timed_validation = None
    if TIME_TAG_RE.search(expected):
        plain = str(proposal.get("plain_lyrics") or strip_lrc(expected)).strip()
        timed_validation = validate_timed_lyrics(
            current["lyrics"], plain, float(current["duration"])
        )
        checks["timed_lyrics_valid"] = bool(timed_validation.get("valid"))
    flags = residual_flags(strip_lrc(current["lyrics"]))
    checks["no_residual_non_lyric_content"] = not flags
    return {
        "schema": "music-lyrics/verification/v1",
        "audio_path": str(audio_path),
        "checks": checks,
        "passed": all(checks.values()),
        "residual_flags": flags,
        "timed_validation": timed_validation,
        "current": current,
        "verified_at": now_iso(),
    }


def verify_track(
    audio_path: Path,
    baseline: dict[str, Any],
    proposal: dict[str, Any],
    backup_path: Path | None,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    """Independently verify one track against a baseline and expected proposal."""

    require_record_audio(baseline, audio_path)
    require_record_audio(proposal, audio_path)
    current = track_snapshot(audio_path, ffmpeg, ffprobe)
    return _verification_result(audio_path, baseline, proposal, current, backup_path)


def report_track(
    audio_path: Path, records: list[dict[str, Any]]
) -> tuple[dict[str, Any], str]:
    """Build one JSON audit and one Markdown report for one track."""

    for record in records:
        require_record_audio(record, audio_path)
    local = metadata(load_audio(audio_path))
    audit = {
        "schema": "music-lyrics/track-audit/v1",
        "audio_path": str(audio_path),
        "metadata": local,
        "records": records,
        "generated_at": now_iso(),
    }
    lines = [
        f"# {local.get('artist') or 'Unknown artist'} — {local.get('title') or audio_path.name}",
        "",
        f"- Audio: `{audio_path}`",
        f"- Album: {local.get('album') or 'Unknown'}",
        f"- Records: {len(records)}",
        "",
        "## Operations",
        "",
    ]
    for record in records:
        schema = str(record.get("schema", "unspecified"))
        status = record.get("status") or record.get("classification")
        passed = record.get("passed")
        details = []
        if status is not None:
            details.append(f"status={status}")
        if passed is not None:
            details.append(f"passed={passed}")
        suffix = f" — {', '.join(details)}" if details else ""
        lines.append(f"- `{schema}`{suffix}")
    lines.append("")
    return audit, "\n".join(lines)


# CLI entry points


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atomic lyric operations for exactly one M4A or MP3 track."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--audio", required=True)
    inspect_parser.add_argument("--ffmpeg", default="ffmpeg")
    inspect_parser.add_argument("--ffprobe", default="ffprobe")
    inspect_parser.add_argument("--output")

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("--audio", required=True)
    search_parser.add_argument(
        "--provider", required=True, choices=("lrclib", "netease")
    )
    search_parser.add_argument("--endpoint", required=True)
    search_parser.add_argument("--query")
    search_parser.add_argument("--limit", type=int, default=20)
    search_parser.add_argument("--timeout", type=float, default=15.0)
    search_parser.add_argument("--user-agent", default="music-track-lyrics/1.0")
    search_parser.add_argument("--output")

    fetch_parser = subparsers.add_parser("fetch")
    fetch_parser.add_argument("--audio", required=True)
    fetch_parser.add_argument("--search-record", required=True)
    fetch_parser.add_argument("--candidate-index", required=True, type=int)
    fetch_parser.add_argument("--endpoint", required=True)
    fetch_parser.add_argument("--timeout", type=float, default=15.0)
    fetch_parser.add_argument("--user-agent", default="music-track-lyrics/1.0")
    fetch_parser.add_argument("--output")

    match_parser = subparsers.add_parser("match")
    match_parser.add_argument("--audio", required=True)
    match_parser.add_argument("--source-record", required=True)
    match_parser.add_argument("--aliases")
    match_parser.add_argument("--duration-tolerance", required=True, type=float)
    match_parser.add_argument("--output")

    clean_parser = subparsers.add_parser("clean")
    clean_parser.add_argument("--audio", required=True)
    clean_parser.add_argument("--lyrics", required=True)
    clean_parser.add_argument(
        "--heading-line",
        action="append",
        type=int,
        default=[],
        help="One-based source line confirmed to be a title heading (repeatable).",
    )
    clean_parser.add_argument("--output")

    segment_parser = subparsers.add_parser("segment")
    segment_parser.add_argument("--audio", required=True)
    segment_parser.add_argument("--lyrics", required=True)
    segment_parser.add_argument("--gap-seconds", required=True, type=float)
    segment_parser.add_argument("--break-before", action="append", type=int, default=[])
    segment_parser.add_argument("--output")

    align_parser = subparsers.add_parser("align")
    align_parser.add_argument("--audio", required=True)
    align_parser.add_argument("--lyrics", required=True)
    align_parser.add_argument("--timed-source", required=True)
    align_parser.add_argument("--minimum-similarity", required=True, type=float)
    align_parser.add_argument("--split-window-seconds", required=True, type=float)
    align_parser.add_argument("--overrides")
    align_parser.add_argument("--output")

    classify_parser = subparsers.add_parser("classify")
    classify_parser.add_argument("--audio", required=True)
    classify_parser.add_argument("--lyrics")
    classify_parser.add_argument("--source-record")
    classify_parser.add_argument("--instrumental-evidence", action="append", default=[])
    classify_parser.add_argument("--output")

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--audio", required=True)
    approve_parser.add_argument("--proposal", required=True)
    approve_parser.add_argument("--match-record")
    approve_parser.add_argument(
        "--decision", required=True, choices=("accept", "reject")
    )
    approve_parser.add_argument("--reviewer", required=True)
    approve_parser.add_argument("--reason", required=True)
    approve_parser.add_argument("--manual-match-override", action="store_true")
    approve_parser.add_argument("--output")

    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("--audio", required=True)
    backup_parser.add_argument("--backup", required=True)
    backup_parser.add_argument("--output")

    write_parser = subparsers.add_parser("write")
    write_parser.add_argument("--audio", required=True)
    write_parser.add_argument("--proposal", required=True)
    write_parser.add_argument("--approval", required=True)
    write_parser.add_argument("--backup", required=True)
    write_parser.add_argument("--ffmpeg", default="ffmpeg")
    write_parser.add_argument("--ffprobe", default="ffprobe")
    write_parser.add_argument("--output")

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--audio", required=True)
    verify_parser.add_argument("--baseline", required=True)
    verify_parser.add_argument("--proposal", required=True)
    verify_parser.add_argument("--backup")
    verify_parser.add_argument("--ffmpeg", default="ffmpeg")
    verify_parser.add_argument("--ffprobe", default="ffprobe")
    verify_parser.add_argument("--output")

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--audio", required=True)
    report_parser.add_argument("--record", action="append", required=True)
    report_parser.add_argument("--json-output", required=True)
    report_parser.add_argument("--markdown-output", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    audio_path = resolve_audio(args.audio)
    if args.command == "inspect":
        result = inspect_track(audio_path, args.ffmpeg, args.ffprobe)
    elif args.command == "search":
        result = search_source(
            audio_path,
            args.provider,
            args.endpoint,
            args.query,
            args.limit,
            args.timeout,
            args.user_agent,
        )
    elif args.command == "fetch":
        result = fetch_source(
            audio_path,
            load_json(args.search_record),
            args.candidate_index,
            args.endpoint,
            args.timeout,
            args.user_agent,
        )
    elif args.command == "match":
        aliases = load_json(args.aliases) if args.aliases else {}
        if not isinstance(aliases, dict):
            raise TypeError("--aliases must contain one JSON object")
        result = match_source(
            audio_path,
            load_json(args.source_record),
            aliases,
            args.duration_tolerance,
        )
    elif args.command == "clean":
        result = clean_track_lyrics(
            audio_path,
            read_lyrics_value(
                args.lyrics,
                ("lyrics", "plain_lyrics", "raw_lyrics", "synchronized_lyrics"),
                audio_path,
            ),
            set(args.heading_line),
        )
    elif args.command == "segment":
        result = segment_track_lyrics(
            audio_path,
            read_lyrics_value(
                args.lyrics,
                ("lyrics", "synchronized_lyrics", "plain_lyrics"),
                audio_path,
            ),
            args.gap_seconds,
            set(args.break_before),
        )
    elif args.command == "align":
        overrides = load_json(args.overrides) if args.overrides else {}
        if not isinstance(overrides, dict):
            raise TypeError("--overrides must contain one JSON object")
        result = align_track_lyrics(
            audio_path,
            read_lyrics_value(args.lyrics, ("lyrics", "plain_lyrics"), audio_path),
            read_lyrics_value(
                args.timed_source,
                ("synchronized_lyrics", "timed_lyrics", "lyrics"),
                audio_path,
            ),
            args.minimum_similarity,
            args.split_window_seconds,
            overrides,
        )
    elif args.command == "classify":
        lyrics = (
            read_lyrics_value(
                args.lyrics,
                ("lyrics", "plain_lyrics", "synchronized_lyrics"),
                audio_path,
            )
            if args.lyrics
            else None
        )
        source_record = load_json(args.source_record) if args.source_record else None
        result = classify_track(
            audio_path, lyrics, source_record, args.instrumental_evidence
        )
    elif args.command == "approve":
        match_record = load_json(args.match_record) if args.match_record else None
        result = approve_change(
            audio_path,
            load_json(args.proposal),
            match_record,
            args.decision,
            args.reviewer,
            args.reason,
            args.manual_match_override,
        )
    elif args.command == "backup":
        result = backup_track(audio_path, Path(args.backup))
    elif args.command == "write":
        result = write_track_lyrics(
            audio_path,
            load_json(args.proposal),
            load_json(args.approval),
            Path(args.backup),
            args.ffmpeg,
            args.ffprobe,
        )
    elif args.command == "verify":
        backup_path = Path(args.backup) if args.backup else None
        result = verify_track(
            audio_path,
            load_json(args.baseline),
            load_json(args.proposal),
            backup_path,
            args.ffmpeg,
            args.ffprobe,
        )
    elif args.command == "report":
        audit, markdown = report_track(
            audio_path, [load_json(path) for path in args.record]
        )
        write_json(audit, args.json_output)
        write_text(markdown, args.markdown_output)
        return
    else:
        raise AssertionError(args.command)
    write_json(result, args.output)


if __name__ == "__main__":
    main()
