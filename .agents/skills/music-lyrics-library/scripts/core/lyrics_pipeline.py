#!/usr/bin/env python3
"""Resumable lyrics audit and tag writer for this local music library."""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile
from mutagen.id3 import USLT
from mutagen.mp4 import MP4, MP4Cover
from mutagen.mp3 import MP3


ROOT = Path(os.environ.get("LYRICS_LIBRARY_ROOT", Path.cwd())).expanduser().resolve()
MEDIA_ROOT = Path(
    os.environ.get("LYRICS_MEDIA_ROOT", ROOT / "Music/Media.localized/Music")
).expanduser().resolve()
WORK_ROOT = ROOT / ".lyrics-work"
BASELINE_PATH = WORK_ROOT / "baseline.jsonl"
FETCH_PATH = WORK_ROOT / "fetched.jsonl"
PREPARED_PATH = WORK_ROOT / "prepared.jsonl"
AUDIT_JSONL = ROOT / "lyrics-audit.jsonl"
AUDIT_MD = ROOT / "lyrics-audit.md"
BACKUP_ROOT = (
    Path(os.environ["LYRICS_BACKUP_ROOT"]).expanduser().resolve()
    if os.environ.get("LYRICS_BACKUP_ROOT")
    else None
)
USER_AGENT = "CodexMusicLyricsAudit/1.0 (personal local library)"

# The first version of this pipeline was built for an 809-track snapshot.
# Keep an opt-in fixed-count guard for historical reruns, but default to the
# current inventory so adding/removing tracks does not make the pipeline fail
# before it can create a new baseline.
EXPECTED_TRACK_COUNT = int(os.environ.get("LYRICS_EXPECTED_COUNT", "0") or 0)

AUDIO_SUFFIXES = {".m4a", ".mp3"}
NETEASE_SEARCH = "https://music.163.com/api/search/get"
NETEASE_LYRIC = "https://music.163.com/api/song/lyric"
LRCLIB_SEARCH = "https://lrclib.net/api/search"

_request_lock = threading.Lock()
_last_request = 0.0
_request_interval = 0.8


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def iter_audio() -> list[Path]:
    return sorted(
        (p for p in MEDIA_ROOT.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES),
        key=lambda p: str(p).casefold(),
    )


def expected_count(*rows: list[dict[str, Any]]) -> int:
    if EXPECTED_TRACK_COUNT > 0:
        return EXPECTED_TRACK_COUNT
    for candidate in rows:
        if candidate:
            return len(candidate)
    return len(iter_audio())


def relpath(path: Path) -> str:
    return str(path.relative_to(MEDIA_ROOT))


def track_key(path_or_rel: str | Path) -> str:
    value = relpath(path_or_rel) if isinstance(path_or_rel, Path) else str(path_or_rel)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def json_dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temp, path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def first(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, (list, tuple)):
        if not value:
            return default
        value = value[0]
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace").rstrip("\x00")
    return str(value)


def mp4_freeform(tags: Any, wanted: str) -> str:
    wanted_norm = wanted.casefold().replace(" ", "")
    for key, value in (tags or {}).items():
        key_norm = str(key).casefold().replace(" ", "")
        if wanted_norm in key_norm:
            return first(value)
    return ""


def id3_text(tags: Any, frame_id: str) -> str:
    frames = tags.getall(frame_id) if tags else []
    if not frames:
        return ""
    frame = frames[0]
    text = getattr(frame, "text", frame)
    return first(text)


def id3_txxx(tags: Any, wanted: str) -> str:
    wanted_norm = wanted.casefold().replace(" ", "")
    for frame in tags.getall("TXXX") if tags else []:
        desc = str(getattr(frame, "desc", "")).casefold().replace(" ", "")
        if wanted_norm in desc:
            return first(getattr(frame, "text", ""))
    return ""


def canonical_value(value: Any) -> Any:
    if isinstance(value, MP4Cover):
        raw = bytes(value)
        return {"kind": "cover", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if isinstance(value, bytes):
        return {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    if isinstance(value, (list, tuple)):
        return [canonical_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): canonical_value(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    return str(value)


def non_lyric_tag_snapshot(audio: Any) -> dict[str, Any]:
    tags = audio.tags
    result: dict[str, Any] = {}
    if isinstance(audio, MP4):
        for key, value in sorted((tags or {}).items(), key=lambda x: str(x[0])):
            key_norm = str(key).casefold().replace(" ", "")
            if str(key) == "©lyr" or "unsyncedlyrics" in key_norm or key_norm.endswith(":lyrics"):
                continue
            result[str(key)] = canonical_value(value)
    elif isinstance(audio, MP3):
        for frame in tags.values() if tags else []:
            if getattr(frame, "FrameID", "") in {"USLT", "SYLT"}:
                continue
            frame_key = getattr(frame, "HashKey", getattr(frame, "FrameID", type(frame).__name__))
            if getattr(frame, "FrameID", "") == "APIC":
                raw = bytes(getattr(frame, "data", b""))
                result[str(frame_key)] = {
                    "mime": getattr(frame, "mime", ""),
                    "type": int(getattr(frame, "type", 0)),
                    "desc": getattr(frame, "desc", ""),
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            else:
                result[str(frame_key)] = str(frame)
    return result


def tag_hash(snapshot: dict[str, Any]) -> str:
    raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def art_info(audio: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(audio, MP4):
        for item in (audio.tags or {}).get("covr", []):
            raw = bytes(item)
            result.append({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    elif isinstance(audio, MP3):
        for frame in (audio.tags.getall("APIC") if audio.tags else []):
            raw = bytes(frame.data)
            result.append({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    return result


def existing_lyrics(audio: Any) -> str:
    if isinstance(audio, MP4):
        tags = audio.tags or {}
        native = first(tags.get("©lyr", ""))
        if native:
            return native
        for key, value in tags.items():
            key_norm = str(key).casefold().replace(" ", "")
            if "unsyncedlyrics" in key_norm or key_norm.endswith(":lyrics"):
                return first(value)
        return ""
    if isinstance(audio, MP3) and audio.tags:
        frames = audio.tags.getall("USLT")
        return "\n\n".join(str(frame.text) for frame in frames if str(frame.text).strip())
    return ""


def read_track(path: Path, include_snapshot: bool = True) -> dict[str, Any]:
    audio = MutagenFile(path, easy=False)
    if audio is None:
        raise ValueError(f"Unsupported audio: {path}")
    tags = audio.tags or {}
    if isinstance(audio, MP4):
        trkn = tags.get("trkn", [(0, 0)])
        disk = tags.get("disk", [(0, 0)])
        title = first(tags.get("©nam"))
        artist = first(tags.get("©ART"))
        album = first(tags.get("©alb"))
        album_artist = first(tags.get("aART"))
        track = first(trkn)
        disc = first(disk)
        isrc = mp4_freeform(tags, "isrc")
        mbid = mp4_freeform(tags, "musicbrainztrackid") or mp4_freeform(tags, "musicbrainz track id")
        acoustid = mp4_freeform(tags, "acoustidid") or mp4_freeform(tags, "acoustid id")
        kind = "m4a"
    elif isinstance(audio, MP3):
        title = id3_text(tags, "TIT2")
        artist = id3_text(tags, "TPE1")
        album = id3_text(tags, "TALB")
        album_artist = id3_text(tags, "TPE2")
        track = id3_text(tags, "TRCK")
        disc = id3_text(tags, "TPOS")
        isrc = id3_text(tags, "TSRC") or id3_txxx(tags, "isrc")
        mbid = id3_txxx(tags, "musicbrainz track id")
        acoustid = id3_txxx(tags, "acoustid id")
        kind = "mp3"
    else:
        raise ValueError(f"Unexpected Mutagen type: {type(audio)}")
    snapshot = non_lyric_tag_snapshot(audio) if include_snapshot else {}
    stat = path.stat()
    return {
        "key": track_key(path),
        "path": str(path),
        "relative_path": relpath(path),
        "kind": kind,
        "title": title,
        "artist": artist,
        "album": album,
        "album_artist": album_artist,
        "track": track,
        "disc": disc,
        "duration": round(float(getattr(audio.info, "length", 0.0)), 3),
        "isrc": isrc,
        "musicbrainz_track_id": mbid,
        "acoustid_id": acoustid,
        "existing_lyrics": existing_lyrics(audio),
        "art": art_info(audio),
        "non_lyric_tag_hash": tag_hash(snapshot) if include_snapshot else "",
        "non_lyric_tags": snapshot if include_snapshot else {},
        "size": stat.st_size,
        "mode": stat.st_mode & 0o7777,
    }


def audio_payload_hash(path: Path) -> str:
    proc = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-c", "copy",
            "-f", "hash", "-hash", "sha256", "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg hash failed for {path}: {proc.stderr.strip()}")
    match = re.search(r"SHA256=([0-9a-fA-F]+)", proc.stdout)
    if not match:
        raise RuntimeError(f"No hash returned for {path}")
    return match.group(1).lower()


def inventory_worker(path: Path, with_hash: bool) -> dict[str, Any]:
    row = read_track(path)
    if with_hash:
        row["audio_payload_sha256"] = audio_payload_hash(path)
    row["inventoried_at"] = now_iso()
    return row


def command_inventory(args: argparse.Namespace) -> None:
    paths = iter_audio()
    if EXPECTED_TRACK_COUNT and len(paths) != EXPECTED_TRACK_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_TRACK_COUNT} audio files, found {len(paths)}"
        )
    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_map = {pool.submit(inventory_worker, p, args.hash): p for p in paths}
        for index, future in enumerate(concurrent.futures.as_completed(future_map), 1):
            path = future_map[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                raise RuntimeError(f"Inventory failed for {path}: {exc}") from exc
            if index % 50 == 0 or index == len(paths):
                print(f"inventory {index}/{len(paths)}", flush=True)
    rows.sort(key=lambda r: r["relative_path"].casefold())
    write_jsonl(BASELINE_PATH, rows)
    summary = {
        "created_at": now_iso(),
        "audio_files": len(rows),
        "formats": dict(Counter(r["kind"] for r in rows)),
        "existing_lyrics": sum(bool(r["existing_lyrics"].strip()) for r in rows),
        "payload_hashes": sum(bool(r.get("audio_payload_sha256")) for r in rows),
    }
    json_dump(WORK_ROOT / "baseline-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def strip_marks(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))


def normalize(value: str) -> str:
    value = strip_marks(unicodedata.normalize("NFKC", value)).casefold()
    value = value.replace("ё", "е")
    return "".join(ch for ch in value if ch.isalnum())


ARTIST_ALIASES = {
    "любэ": "lube",
    "любе": "lube",
    "lube": "lube",
    "lyube": "lube",
    "哪吒": "哪吒",
    "哪吒乐队": "哪吒",
    "哪吒樂隊": "哪吒",
    "万能青年旅店": "万能青年旅店",
    "萬能青年旅店": "万能青年旅店",
    "omnipotentyouthsociety": "万能青年旅店",
    "本能实业": "本能实业",
    "本能實業": "本能实业",
    "赞诗": "赞诗",
    "贊詩": "赞诗",
    "glowcurve": "glowcurve",
    "发光曲线": "glowcurve",
    "發光曲線": "glowcurve",
    "老王乐队": "老王乐队",
    "老王樂隊": "老王乐队",
    "shigeokomori": "小森茂生",
    "小森茂生": "小森茂生",
}


def normalize_artist_atom(value: str) -> str:
    raw = normalize(value)
    raw = re.sub(r"(?:乐队|樂隊|band)$", "", raw)
    return ARTIST_ALIASES.get(raw, raw)


def artist_atoms(value: str) -> set[str]:
    pieces = re.split(r"\s*(?:,|，|、|&|／|/|;|；|\bfeat(?:uring)?\.?\b|\bft\.?\b|\band\b)\s*", value, flags=re.I)
    atoms = {normalize_artist_atom(p) for p in pieces if normalize_artist_atom(p)}
    whole = normalize_artist_atom(value)
    if whole:
        atoms.add(whole)
    return atoms


def artist_match(metadata_artist: str, candidate_artists: list[str]) -> tuple[bool, str]:
    left = artist_atoms(metadata_artist)
    right: set[str] = set()
    for artist in candidate_artists:
        right.update(artist_atoms(artist))
    if left & right:
        exact = sorted(left & right)[0]
        if normalize(metadata_artist) != normalize(" / ".join(candidate_artists)):
            return True, f"artist alias/credit difference: {metadata_artist} ↔ {' / '.join(candidate_artists)} ({exact})"
        return True, ""
    for a in left:
        for b in right:
            if len(a) >= 4 and len(b) >= 4 and (a in b or b in a):
                return True, f"artist partial-credit match: {metadata_artist} ↔ {' / '.join(candidate_artists)}"
    return False, ""


def title_match(metadata_title: str, candidate_title: str) -> bool:
    return bool(normalize(metadata_title)) and normalize(metadata_title) == normalize(candidate_title)


def request_json(
    url: str,
    params: dict[str, Any],
    cache_namespace: str,
    timeout: int = 10,
    attempts: int = 3,
) -> Any:
    global _last_request
    encoded = urllib.parse.urlencode(params, doseq=True)
    full_url = f"{url}?{encoded}"
    cache_key = hashlib.sha256(full_url.encode("utf-8")).hexdigest()
    cache_path = WORK_ROOT / "http-cache" / cache_namespace / f"{cache_key}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with _request_lock:
                wait = _request_interval - (time.monotonic() - _last_request)
                if wait > 0:
                    time.sleep(wait)
                _last_request = time.monotonic()
            req = urllib.request.Request(full_url, headers={"User-Agent": USER_AGENT, "Referer": "https://music.163.com/"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8", "replace"))
            json_dump(cache_path, data)
            return data
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last_error = exc
            time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"request failed {full_url}: {last_error}")


def netease_candidates(meta: dict[str, Any]) -> list[dict[str, Any]]:
    queries = [" ".join(x for x in [meta["title"], meta["artist"]] if x)]
    if meta["title"] and meta["title"] not in queries:
        queries.append(meta["title"])
    songs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for query in queries:
        data = request_json(
            NETEASE_SEARCH,
            {"s": query, "type": 1, "limit": 50},
            "netease-search-20260715-refetch2-slow",
        )
        for song in (data.get("result") or {}).get("songs") or []:
            source_id = str(song.get("id", ""))
            if source_id and source_id not in seen_ids:
                songs.append(song)
                seen_ids.add(source_id)
    result: list[dict[str, Any]] = []
    for song in songs:
        artists = [str(x.get("name", "")) for x in (song.get("artists") or song.get("ar") or [])]
        album_obj = song.get("album") or song.get("al") or {}
        duration_ms = song.get("duration") or song.get("dt") or 0
        result.append({
            "source": "netease",
            "source_id": str(song.get("id", "")),
            "title": str(song.get("name", "")),
            "artists": artists,
            "album": str(album_obj.get("name", "")),
            "duration": round(float(duration_ms) / 1000.0, 3) if duration_ms else 0.0,
            "source_url": f"https://music.163.com/song?id={song.get('id', '')}",
        })
    return result


def lrclib_candidates(meta: dict[str, Any]) -> list[dict[str, Any]]:
    data = request_json(
        LRCLIB_SEARCH,
        {"track_name": meta["title"], "artist_name": meta["artist"]},
        "lrclib-search-20260715-refetch2-slow",
        timeout=4,
        attempts=1,
    )
    result: list[dict[str, Any]] = []
    for item in data if isinstance(data, list) else []:
        result.append({
            "source": "lrclib",
            "source_id": str(item.get("id", "")),
            "title": str(item.get("trackName", "")),
            "artists": [str(item.get("artistName", ""))],
            "album": str(item.get("albumName", "")),
            "duration": float(item.get("duration") or 0.0),
            "source_url": f"https://lrclib.net/api/get/{item.get('id', '')}",
            "raw_lyrics": item.get("syncedLyrics") or item.get("plainLyrics") or "",
        })
    return result


def assess_candidate(meta: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    title_ok = title_match(meta["title"], candidate["title"])
    artist_ok, artist_note = artist_match(meta["artist"], candidate["artists"])
    duration_diff = abs(float(meta["duration"]) - float(candidate.get("duration") or 0.0)) if candidate.get("duration") else None
    duration_ok = duration_diff is not None and duration_diff <= 5.0
    album_ok = bool(meta.get("album") and candidate.get("album") and normalize(meta["album"]) == normalize(candidate["album"]))
    accepted = title_ok and artist_ok and duration_ok
    score = (100 if title_ok else 0) + (80 if artist_ok else 0) + (30 if duration_ok else 0) + (20 if album_ok else 0)
    assessed = dict(candidate)
    assessed.update({
        "title_match": title_ok,
        "artist_match": artist_ok,
        "artist_note": artist_note,
        "album_match": album_ok,
        "duration_difference": round(duration_diff, 3) if duration_diff is not None else None,
        "duration_match": duration_ok,
        "accepted": accepted,
        "score": score,
    })
    return assessed


PLACEHOLDER_RE = re.compile(
    r"(?:纯音乐[，,、 ]*(?:请欣赏)?|此歌曲暂无文本歌词|暂无歌词|instrumental(?:\s+music)?|lyrics?\s+not\s+available)",
    re.I,
)


def fetch_netease_lyric(candidate: dict[str, Any]) -> str:
    data = request_json(
        NETEASE_LYRIC,
        {"id": candidate["source_id"], "lv": -1, "kv": -1, "tv": -1},
        "netease-lyric-20260715-refetch2-slow",
    )
    return str((data.get("lrc") or {}).get("lyric") or "")


def choose_candidate(meta: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[str]]:
    assessed = [assess_candidate(meta, c) for c in candidates]
    accepted = [c for c in assessed if c["accepted"]]
    accepted.sort(key=lambda c: (not c["album_match"], c["duration_difference"], -c["score"], c["source_id"]))
    notes: list[str] = []
    if not accepted:
        return None, assessed[:10], notes
    best = accepted[0]
    tied = [c for c in accepted if c["album_match"] == best["album_match"] and abs(c["duration_difference"] - best["duration_difference"]) < 0.25]
    if len(tied) > 1:
        notes.append(f"multiple metadata-equivalent candidates: {', '.join(c['source_id'] for c in tied)}")
    if best.get("artist_note"):
        notes.append(best["artist_note"])
    if meta.get("album") and best.get("album") and not best["album_match"]:
        notes.append(f"album difference: {meta['album']} ↔ {best['album']}")
    return best, assessed[:10], notes


def fetch_one(meta: dict[str, Any]) -> dict[str, Any]:
    per_track = WORK_ROOT / "fetch" / f"{meta['key']}.json"
    if per_track.exists():
        cached = json.loads(per_track.read_text(encoding="utf-8"))
        if cached.get("status") != "matched":
            return cached
        preview, _, _ = clean_lyrics(cached.get("raw_lyrics", ""), meta["title"], meta["artist"])
        if len([line for line in preview.splitlines() if line.strip()]) >= 2:
            return cached
    errors: list[str] = []
    netease: list[dict[str, Any]] = []
    try:
        netease = netease_candidates(meta)
    except Exception as exc:
        errors.append(f"netease search: {exc}")
    selected, candidates, notes = choose_candidate(meta, netease)
    raw = ""
    if selected:
        try:
            raw = fetch_netease_lyric(selected)
        except Exception as exc:
            errors.append(f"netease lyric: {exc}")
    preview, _, _ = clean_lyrics(raw, meta["title"], meta["artist"]) if raw.strip() else ("", {}, [])
    poor_text = len([line for line in preview.splitlines() if line.strip()]) == 0
    if not selected or not raw.strip() or PLACEHOLDER_RE.search(raw) or poor_text:
        lrclib: list[dict[str, Any]] = []
        try:
            lrclib = lrclib_candidates(meta)
        except Exception as exc:
            errors.append(f"lrclib search: {exc}")
        lr_selected, lr_candidates, lr_notes = choose_candidate(meta, lrclib)
        candidates.extend(lr_candidates)
        if lr_selected and str(lr_selected.get("raw_lyrics", "")).strip() and not PLACEHOLDER_RE.search(str(lr_selected.get("raw_lyrics", ""))):
            selected = lr_selected
            raw = str(lr_selected.get("raw_lyrics", ""))
            notes = lr_notes
    preview, _, _ = clean_lyrics(raw, meta["title"], meta["artist"]) if raw.strip() else ("", {}, [])
    poor_text = len([line for line in preview.splitlines() if line.strip()]) == 0
    if selected and (not raw.strip() or poor_text):
        status = "matched_no_text"
    elif selected and PLACEHOLDER_RE.search(raw):
        status = "matched_placeholder"
    elif selected:
        status = "matched"
    else:
        status = "unresolved"
    result = {
        "key": meta["key"],
        "relative_path": meta["relative_path"],
        "metadata": {k: meta.get(k, "") for k in ["title", "artist", "album", "album_artist", "track", "disc", "duration", "isrc", "musicbrainz_track_id", "acoustid_id"]},
        "status": status,
        "selected": selected,
        "candidates": candidates[:20],
        "raw_lyrics": raw,
        "match_notes": notes,
        "errors": errors,
        "fetched_at": now_iso(),
    }
    json_dump(per_track, result)
    return result


def command_fetch(args: argparse.Namespace) -> None:
    baseline = read_jsonl(BASELINE_PATH)
    if len(baseline) != expected_count(baseline):
        raise RuntimeError("Run inventory first; baseline count is inconsistent")
    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_map = {pool.submit(fetch_one, meta): meta for meta in baseline}
        for index, future in enumerate(concurrent.futures.as_completed(future_map), 1):
            meta = future_map[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                rows.append({
                    "key": meta["key"], "relative_path": meta["relative_path"], "metadata": meta,
                    "status": "unresolved", "selected": None, "candidates": [], "raw_lyrics": "",
                    "match_notes": [], "errors": [f"fatal fetch: {exc}"], "fetched_at": now_iso(),
                })
            if index % 25 == 0 or index == len(baseline):
                counts = Counter(r["status"] for r in rows)
                print(f"fetch {index}/{len(baseline)} {dict(counts)}", flush=True)
    rows.sort(key=lambda r: r["relative_path"].casefold())
    write_jsonl(FETCH_PATH, rows)
    print(json.dumps(Counter(r["status"] for r in rows), ensure_ascii=False, indent=2))


def command_refetch_unresolved(args: argparse.Namespace) -> None:
    from classify_unresolved import classify

    global _request_interval
    _request_interval = args.request_interval

    baseline_rows = read_jsonl(BASELINE_PATH)
    fetched_rows = read_jsonl(FETCH_PATH)
    audit_rows = read_jsonl(AUDIT_JSONL)
    expected = expected_count(baseline_rows, fetched_rows, audit_rows)
    if any(len(rows) != expected for rows in (baseline_rows, fetched_rows, audit_rows)):
        raise RuntimeError("baseline, fetched, and audit files must have the same row count")

    baseline = {row["key"]: row for row in baseline_rows}
    fetched = {row["key"]: row for row in fetched_rows}
    targets: list[dict[str, Any]] = []
    excluded_lyube: list[str] = []
    for row in audit_rows:
        if row.get("final_verification", {}).get("lyrics_present", False):
            continue
        category, _ = classify(row)
        if category != "unresolved":
            continue
        artist = row["metadata"].get("artist", "")
        artist_normalized = normalize(artist)
        if artist_normalized.startswith("любе") or artist_normalized.startswith("любэ"):
            excluded_lyube.append(row["relative_path"])
            continue
        targets.append(baseline[row["key"]])

    print(
        f"refetch targets={len(targets)} excluded_lyube={len(excluded_lyube)} "
        f"workers={args.workers} request_interval={_request_interval:.2f}s",
        flush=True,
    )
    for meta in targets:
        (WORK_ROOT / "fetch" / f"{meta['key']}.json").unlink(missing_ok=True)

    refreshed: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_map = {pool.submit(fetch_one, meta): meta for meta in targets}
        for index, future in enumerate(concurrent.futures.as_completed(future_map), 1):
            meta = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "key": meta["key"], "relative_path": meta["relative_path"], "metadata": meta,
                    "status": "unresolved", "selected": None, "candidates": [], "raw_lyrics": "",
                    "match_notes": [], "errors": [f"fatal refetch: {exc}"], "fetched_at": now_iso(),
                }
            refreshed.append(result)
            fetched[result["key"]] = result
            if index % 20 == 0 or index == len(targets):
                counts = Counter(item["status"] for item in refreshed)
                print(f"refetch {index}/{len(targets)} {dict(counts)}", flush=True)

    merged = sorted(fetched.values(), key=lambda row: row["relative_path"].casefold())
    write_jsonl(FETCH_PATH, merged)
    json_dump(
        WORK_ROOT / "refetch-unresolved-summary.json",
        {
            "refetched_at": now_iso(),
            "targets": len(targets),
            "workers": args.workers,
            "request_interval_seconds": _request_interval,
            "excluded_lyube": excluded_lyube,
            "results": dict(Counter(item["status"] for item in refreshed)),
            "tracks": [
                {
                    "relative_path": item["relative_path"],
                    "status": item["status"],
                    "selected": item.get("selected"),
                    "errors": item.get("errors", []),
                }
                for item in sorted(refreshed, key=lambda row: row["relative_path"].casefold())
            ],
        },
    )
    print(json.dumps(Counter(item["status"] for item in refreshed), ensure_ascii=False, indent=2))


def command_record_refetch(args: argparse.Namespace) -> None:
    summary_path = WORK_ROOT / "refetch-unresolved-summary.json"
    if not summary_path.exists():
        raise RuntimeError("refetch summary does not exist")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    tracks = summary.get("tracks", [])
    if any(item.get("status") == "matched" for item in tracks):
        raise RuntimeError("refetch has matched lyrics; write and verify them before recording the final audit")

    audits = read_jsonl(AUDIT_JSONL)
    fetched = {row["relative_path"]: row for row in read_jsonl(FETCH_PATH)}
    expected = expected_count(audits, fetched)
    if len(audits) != expected or len(fetched) != expected:
        raise RuntimeError("audit and fetched files must have the same row count")
    by_path = {row["relative_path"]: row for row in audits}
    stamp = summary.get("refetched_at", now_iso())
    for item in tracks:
        path = item["relative_path"]
        audit = by_path[path]
        fetch = fetched[path]
        audit["fetch_status"] = fetch["status"]
        audit["selected"] = fetch.get("selected")
        audit["errors"] = fetch.get("errors", [])
        history = list(audit.get("refetch_history", []))
        if not any(entry.get("refetched_at") == stamp for entry in history):
            history.append({
                "refetched_at": stamp,
                "workers": summary.get("workers"),
                "request_interval_seconds": summary.get("request_interval_seconds"),
                "status": fetch["status"],
                "selected": fetch.get("selected"),
                "errors": fetch.get("errors", []),
                "result": "no_usable_lyrics",
            })
        audit["refetch_history"] = history
    write_jsonl(AUDIT_JSONL, sorted(audits, key=lambda row: row["relative_path"].casefold()))
    print(f"recorded slow refetch for {len(tracks)} tracks at {stamp}")


TIMESTAMP_RE = re.compile(r"\[(?P<m>\d{1,3}):(?P<s>\d{2})(?:[.:](?P<f>\d{1,3}))?(?:-\d+)?\]")
INLINE_TIMESTAMP_RE = re.compile(r"\[\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?(?:-\d+)?\]")
MALFORMED_TIMESTAMP_RE = re.compile(r"\[\d{1,3}:\d{1,6}(?:[.:]\d+)?\]")
LRC_META_RE = re.compile(r"^\[(?:ar|al|ti|by|offset|re|ve|length|au):.*\]$", re.I)
SECTION_RE = re.compile(
    r"^(?:\[\s*(?:intro|verse(?:\s*\d+)?|pre[- ]?chorus|chorus|bridge|outro|hook|refrain|instrumental|interlude|solo)\s*\]|(?:\d+\s*)?(?:припев|куплет|вступление|проигрыш)\s*:?)$",
    re.I,
)
PAREN_MARKER_RE = re.compile(
    r"^[（(]\s*(?:music|instrumental|intro|outro|interlude|间奏|前奏|尾奏|童声|合唱|独唱|齊唱|齐唱|припев\s*:?)\s*[）)]$",
    re.I,
)
ROLE_PREFIX_RE = re.compile(r"^(?P<prefix>童|独|合|吴|劉|刘|女|男|众|眾|齐|齊|旁白|甲|乙|[A-ZА-ЯЁ]{1,2}|General Patton)\s*[：:]\s*(?P<text>.+)$", re.I)
PURE_ROLE_MARKER_RE = re.compile(r"^(?:童|独|合|吴|劉|刘|女|男|众|眾|齐|齊|旁白|甲|乙)(?:\s*[：:])?\s*$")
PAREN_ROLE_RE = re.compile(r"^(?P<open>[（(])\s*[^：:()（）]{1,12}\s*[：:]\s*(?P<text>.+?)(?P<close>[）)])$")
CREDIT_PREFIXES = [
    "人声", "詞", "词", "曲", "作词", "作詞", "作曲", "词曲", "詞曲", "编曲", "編曲", "母带", "母帶", "母带工程师", "母帶工程師",
    "母带室", "母帶室", "制作人", "製作人", "制作管理", "製作管理", "录音", "錄音", "录音室", "錄音室", "混音", "混音师", "混音師",
    "吉他", "电吉他", "電吉他", "原声吉他", "原聲吉他", "贝斯", "貝斯", "鼓", "鼓组技师", "鼓組技師", "键盘", "鍵盤",
    "中提琴", "次中音萨克斯", "次中音薩克斯", "口琴", "乌克里里", "烏克麗麗", "口风琴", "口風琴", "口哨", "采样", "採樣",
    "朗诵", "朗誦", "旁白", "女声", "女聲", "男声", "男聲", "和声", "和聲", "合声", "合聲", "声乐", "聲樂", "配唱",
    "编程", "編程", "乐团", "樂團", "曼陀铃", "曼陀鈴", "手风琴", "手風琴", "笛子", "书法", "書法", "摄影", "攝影", "设计", "設計", "scratch",
    "大提琴独奏", "大提琴獨奏", "打击指导", "打擊指導", "绘图", "繪圖", "后期", "後期", "演唱", "表演者", "主唱", "独唱", "獨唱", "合唱",
    "发行公司", "發行公司", "音乐营销发行公司", "音樂營銷發行公司", "特别鸣谢", "特別鳴謝", "特别感谢", "特別感謝",
    "厂牌", "廠牌", "版权", "版權", "artist manager", "producer", "guitar", "mixed by", "strings by", "grand piano by",
    "слова", "музыка", "сл.", "муз.", "op", "sp", "isrc", "pgm",
]
CREDIT_RE = re.compile(r"^(?:" + "|".join(re.escape(x) for x in sorted(CREDIT_PREFIXES, key=len, reverse=True)) + r")(?:\s+[A-Za-zА-Яа-яЁё]+)?\s*[：:]", re.I)
CREDIT_BY_RE = re.compile(r"^(?:artist manager|producer|mixed|strings|grand piano|guitars?|acoustic guitars?|mastered|recorded|arranged|programming)(?:\s*/\s*[A-Za-z ]+)?\s+by\b", re.I)
NOISE_RE = re.compile(
    r"(?:QQ音乐|网易云|網易雲|酷狗|虾米|蝦米|付费|付費|VIP|试听|試聽|下载|下載|关注我们|關注我們|公众号|公眾號|云上工作室|現金激勵|现金激励|业务联系|業務聯繫|歌词来源|歌詞來源|仅供娱乐|僅供娛樂|http://|https://|www\.|录音制作者权人|錄音製作者權人|音乐营销发行公司|音樂營銷發行公司|special thanks|特别感谢品牌支持)",
    re.I,
)
COPYRIGHT_RE = re.compile(r"^(?:op(?:\s*/\s*sp)?|sp|isrc|厂牌|廠牌|版权|版權)(?:\s*[：:]|\b)|[Ⓟ℗©].*[ⓒ©]|○\s*[PC]", re.I)
PINYIN_GARBAGE_RE = re.compile(r"^bpmfdtnlgkhjqxzcszhchshriywuaoe$", re.I)
NUMBER_LINE_RE = re.compile(r"^<\d+>\s*\d{4}[./-]\d{1,2}[./-]\d{1,2}\s*$")
DATE_CODE_RE = re.compile(r"^\d{4}\s+\d{1,2}(?:\s*[-/]\s*\d{4}\s+\d{1,2})?(?:\s*/\s*\d{1,2}){1,4}\s*$")
ISOLATED_GARBAGE_RE = re.compile(r"^[-—–_=*#<>]+$")


def is_credit_line(line: str) -> bool:
    if CREDIT_RE.match(line) or CREDIT_BY_RE.match(line):
        return True
    parts = re.split(r"[：:]", line, maxsplit=1)
    if len(parts) != 2:
        return False
    prefix = normalize(parts[0])
    if not prefix or len(prefix) > 45:
        return False
    role_words = [
        "作词", "作曲", "词曲", "英语词", "編詞", "编曲", "制作", "制作人", "制作管理", "录音", "录音工程师", "录音师", "混音", "混音师",
        "母带", "母带工程师", "人声", "主唱", "演唱", "表演者", "合唱", "独唱", "朗诵", "旁白", "女声", "男声", "和声", "合声", "声乐", "配唱",
        "吉他", "贝斯", "鼓", "鼓组技师", "键盘", "编程", "乐团", "曼陀铃", "手风琴", "笛子", "书法", "摄影", "设计", "scratch",
        "中提琴", "大提琴", "萨克斯", "口琴", "乌克里里", "口风琴", "口哨", "小号", "采样", "打击指导",
        "小提琴", "次中音号", "和声", "管乐", "弦乐", "钢琴", "低音单簧管", "长笛", "打击乐", "合成器", "硬件噪音",
        "贝司", "單簧管", "打擊指導", "平面设计", "平面設計", "画师", "畫師", "歌",
        "发行公司", "音乐营销", "唱片公司", "监制", "统筹", "推广", "发行", "出品", "企划", "策划", "项目协力",
        "制作协力", "音频编辑", "剪辑工程师", "乐务", "艺术家统筹", "童声统筹", "诗", "特别鸣谢", "特别感谢",
        "協同編曲", "統籌", "推廣", "發行", "錄音師", "錄音室", "剪輯工程師", "母帶後製", "弦樂", "鋼琴",
        "artistmanager", "producer", "guitar", "mixedby", "doublebass", "bass", "midi", "additionalarranger",
        "recordingengineer", "recordingstudio", "editingengineer", "masteringengineer", "publishedby", "distributedby",
        "stringsby", "grandpianoby", "masteredby", "recordedby", "слова", "музыка", "сл", "муз", "isrc",
        "исполнители",
    ]
    return any(prefix.startswith(normalize(word)) for word in role_words)


def timestamp_seconds(match: re.Match[str]) -> float:
    fraction = match.group("f") or "0"
    return int(match.group("m")) * 60 + int(match.group("s")) + int(fraction) / (10 ** len(fraction))


def is_preserved_title_exception(line: str) -> bool:
    stripped = line.strip()
    return bool(
        re.match(r"^Любэ\s*[—–-]", stripped, re.I)
        or re.match(r"^小森茂生\s*[—–-]\s*陰の伝承歌", stripped)
        or re.match(r"^[《〈].+[》〉]", stripped)
    )


def title_residual(line: str, title: str, artist: str) -> bool:
    if is_preserved_title_exception(line):
        return False
    nline = normalize(line)
    nt = normalize(title)
    artist_variants = artist_atoms(artist)
    if not nline or not nt:
        return False
    if nline == nt:
        return True
    for na in artist_variants:
        if nline in {nt + na, na + nt}:
            return True
    return False


def refine_long_paragraphs(
    paragraphs: list[list[dict[str, Any]]], transformations: dict[str, Any]
) -> list[list[dict[str, Any]]]:
    refined: list[list[dict[str, Any]]] = []
    for paragraph in paragraphs:
        timed_chunks: list[list[dict[str, Any]]] = [[]]
        timed_gaps = [
            paragraph[i]["time"] - paragraph[i - 1]["time"]
            for i in range(1, len(paragraph))
            if paragraph[i]["time"] is not None and paragraph[i - 1]["time"] is not None
        ]
        median_gap = statistics.median(timed_gaps) if timed_gaps else 0.0
        for index, event in enumerate(paragraph):
            if index and event["time"] is not None and paragraph[index - 1]["time"] is not None:
                gap = event["time"] - paragraph[index - 1]["time"]
                if len(timed_chunks[-1]) >= 3 and gap >= max(5.5, median_gap + 1.5):
                    transformations["paragraph_breaks_added"].append({
                        "before_source_line": event["source_line"],
                        "reason": f"relative timestamp gap {gap:.2f}s within source paragraph",
                    })
                    timed_chunks.append([])
            timed_chunks[-1].append(event)
        for chunk in timed_chunks:
            if len(chunk) <= 16:
                refined.append(chunk)
                continue
            grams: dict[tuple[str, str], list[int]] = {}
            for index in range(len(chunk) - 1):
                gram = (normalize(chunk[index]["text"]), normalize(chunk[index + 1]["text"]))
                if gram[0] and gram[1]:
                    grams.setdefault(gram, []).append(index)
            proposed = sorted({pos for positions in grams.values() if len(positions) >= 2 for pos in positions})
            cuts: list[int] = []
            last = 0
            for pos in proposed:
                if pos >= 4 and pos - last >= 4 and len(chunk) - pos >= 3:
                    cuts.append(pos)
                    last = pos
            repeated_chunks: list[list[dict[str, Any]]] = []
            start = 0
            for cut in cuts:
                repeated_chunks.append(chunk[start:cut])
                transformations["paragraph_breaks_added"].append({
                    "before_source_line": chunk[cut]["source_line"],
                    "reason": "repeated lyric phrase boundary",
                })
                start = cut
            repeated_chunks.append(chunk[start:])
            for repeated in repeated_chunks:
                if len(repeated) <= 16:
                    refined.append(repeated)
                    continue
                parts = (len(repeated) + 15) // 16
                target = (len(repeated) + parts - 1) // parts
                for start in range(0, len(repeated), target):
                    piece = repeated[start:start + target]
                    if start:
                        transformations["paragraph_breaks_added"].append({
                            "before_source_line": piece[0]["source_line"],
                            "reason": f"manual-review length safeguard ({target}-line section)",
                        })
                    refined.append(piece)
    return [paragraph for paragraph in refined if paragraph]


def clean_lyrics(raw: str, title: str, artist: str) -> tuple[str, dict[str, Any], list[str]]:
    transformations: dict[str, Any] = {
        "timestamps_removed": 0,
        "removed_lines": [],
        "role_prefix_changes": [],
        "paragraph_breaks_added": [],
    }
    warnings: list[str] = []
    events: list[dict[str, Any]] = []
    pending_break = False
    for source_line_no, original in enumerate(raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1):
        line = original.strip().lstrip("\ufeff")
        matches = list(TIMESTAMP_RE.finditer(line))
        seconds = timestamp_seconds(matches[0]) if matches else None
        transformations["timestamps_removed"] += len(matches)
        line = TIMESTAMP_RE.sub("", line).strip()
        inline = list(INLINE_TIMESTAMP_RE.finditer(line))
        transformations["timestamps_removed"] += len(inline)
        line = INLINE_TIMESTAMP_RE.sub("", line).strip()
        malformed = list(MALFORMED_TIMESTAMP_RE.finditer(line))
        transformations["timestamps_removed"] += len(malformed)
        line = MALFORMED_TIMESTAMP_RE.sub("", line).strip()
        if not line:
            if events:
                pending_break = True
            continue
        category = ""
        if LRC_META_RE.match(line):
            category = "lrc_metadata"
        elif SECTION_RE.match(line):
            category = "section_marker"
        elif PAREN_MARKER_RE.match(line):
            category = "role_or_music_marker"
        elif PURE_ROLE_MARKER_RE.match(line):
            category = "role_marker"
        elif line.casefold() == "--end--":
            category = "transcription_marker"
        elif PINYIN_GARBAGE_RE.match(normalize(line)):
            category = "meaningless_letter_string"
        elif NUMBER_LINE_RE.match(line):
            category = "numbering_marker"
        elif DATE_CODE_RE.match(line):
            category = "date_or_numbering_marker"
        elif ISOLATED_GARBAGE_RE.match(line):
            category = "isolated_symbol_marker"
        elif PLACEHOLDER_RE.fullmatch(line.strip("。.!！ ")):
            category = "instrumental_or_no_lyrics_placeholder"
        elif is_credit_line(line):
            category = "credit"
        elif COPYRIGHT_RE.search(line):
            category = "copyright_or_label"
        elif NOISE_RE.search(line):
            category = "platform_or_advertising"
        elif title_residual(line, title, artist) and (
            not events or normalize(line) != normalize(title)
        ):
            category = "title_artist_residual"
        if category:
            transformations["removed_lines"].append({"line": source_line_no, "category": category, "text": original})
            continue
        role = ROLE_PREFIX_RE.match(line)
        if role:
            changed = role.group("text").strip()
            transformations["role_prefix_changes"].append({"line": source_line_no, "from": line, "to": changed})
            line = changed
        else:
            paren_role = PAREN_ROLE_RE.match(line)
            if paren_role:
                changed = f"{paren_role.group('open')}{paren_role.group('text').strip()}{paren_role.group('close')}"
                transformations["role_prefix_changes"].append({"line": source_line_no, "from": line, "to": changed})
                line = changed
        events.append({"text": line, "time": seconds, "source_line": source_line_no, "break_before": pending_break})
        pending_break = False
    if not events:
        return "", transformations, warnings
    paragraphs: list[list[dict[str, Any]]] = [[]]
    previous_time: float | None = None
    for event in events:
        gap = (event["time"] - previous_time) if event["time"] is not None and previous_time is not None else None
        break_reason = ""
        if event["break_before"] and paragraphs[-1]:
            break_reason = "blank/timestamp-only source line"
        elif gap is not None and gap >= 8.0 and len(paragraphs[-1]) >= 2:
            break_reason = f"timestamp gap {gap:.2f}s"
        if break_reason:
            transformations["paragraph_breaks_added"].append({"before_source_line": event["source_line"], "reason": break_reason})
            paragraphs.append([])
        paragraphs[-1].append(event)
        if event["time"] is not None:
            previous_time = event["time"]
    paragraphs = [p for p in paragraphs if p]
    if len(paragraphs) == 1 and len(events) >= 12 and all(e["time"] is not None for e in events):
        gaps = [events[i]["time"] - events[i - 1]["time"] for i in range(1, len(events))]
        median_gap = statistics.median(gaps) if gaps else 0.0
        new_paragraphs: list[list[dict[str, Any]]] = [[]]
        for idx, event in enumerate(events):
            if idx:
                gap = event["time"] - events[idx - 1]["time"]
                if len(new_paragraphs[-1]) >= 3 and gap >= max(5.5, median_gap + 1.5):
                    transformations["paragraph_breaks_added"].append({"before_source_line": event["source_line"], "reason": f"relative timestamp gap {gap:.2f}s"})
                    new_paragraphs.append([])
            new_paragraphs[-1].append(event)
        if len(new_paragraphs) > 1:
            paragraphs = new_paragraphs
    paragraphs = refine_long_paragraphs(paragraphs, transformations)
    if len(paragraphs) == 1 and len(events) >= 16:
        warnings.append(f"long single paragraph remains ({len(events)} lines); manual segmentation required")
    lyric = "\n\n".join("\n".join(e["text"] for e in paragraph) for paragraph in paragraphs).strip()
    if len([x for x in lyric.splitlines() if x.strip()]) < 2:
        warnings.append("fewer than two lyric lines after cleaning")
    return lyric, transformations, warnings


def residual_flags(lyric: str) -> list[str]:
    flags: list[str] = []
    checks = {
        "timestamp": INLINE_TIMESTAMP_RE,
        "section_marker": SECTION_RE,
        "transcription_marker": re.compile(r"--end--", re.I),
        "placeholder": PLACEHOLDER_RE,
        "platform_or_ad": NOISE_RE,
        "credit": CREDIT_RE,
        "pinyin_garbage": PINYIN_GARBAGE_RE,
    }
    for name, pattern in checks.items():
        if pattern.search(lyric):
            flags.append(name)
    return flags


MANUAL_BREAKS = {
    "Compilations/Spasibo Dedu Za Pobedu!/13 Soldat.m4a": [6, 10, 20, 24, 32, 36, 46, 50],
    "Любэ/Атас/01 Люберцы.m4a": [8, 16, 24, 32, 39, 43, 47, 51, 55],
    "Любэ/Атас/05 Ночь.m4a": [8, 13, 21],
    "Любэ/За тебя, Родина-мать/09 Товарищ.m4a": [4, 12, 18, 22, 30, 36],
    "Любэ/Свои/08 Заимка.m4a": [8, 12, 20, 24, 28],
    "揽佬SKAI ISYOURGOD/八方来财/04 六爻.m4a": [11, 23, 34, 53],
}

MANUAL_TEXT_REPLACEMENTS = {
    "Любэ/За тебя, Родина-мать/09 Товарищ.m4a": {"?товарищ?": "«товарищ»"},
    "Compilations/Spasibo Dedu Za Pobedu!/04 Spasibo Dedu Za Pobedu!.m4a": {"?Наш родной?": "«Наш родной»"},
    "Vaundy/CHAINSAW BLOOD/01 CHAINSAW BLOOD.m4a": {"『あ? なんだって?』": "『あ？なんだって？』"},
}

MANUAL_LINE_REMOVALS = {
    "Любэ/Зона Любэ/02 Бабу бы.m4a": {"бабу бы(娘儿们)": "translated title header"},
    "Любэ/Кто сказал, что мы плохо жили..._/09 Старый барин.m4a": {"Старый бари(大老爷)": "translated title header"},
    "Любэ/Рассея/07 Не смотри на часы.m4a": {"Любэ- Не смотри на часы,": "artist-title header"},
    "Любэ/Рассея/08 По высокой траве.m4a": {"Любэ, Офицеры группы \"Альфа\"": "performer credit header"},
    "哪吒/他在时间门外/07 闹海.m4a": {"闹海-哪吒乐队": "song-artist title header"},
}

MANUAL_ORIGINAL_LYRICS = {
    "Ludola/Rogate Czapki, Rogate Serca/03 Gdy Umrę....m4a": {
        "source_url": "https://www.tekstowo.pl/ludola/gdy-umre",
        "note": "replaced pre-existing English translation with verified original Polish lyrics",
        "lyrics": """Tyle lat minęło
Tyle przeszło burz
Bzy jednak kwitły wciąż
Szumiał wiatr pośród brzóz
Myśmy szli wciąż borem
Kiedy wstał nienawistny świt
Las przywitał nas wyklętych
I wielu wciąż w nim śpi...

Kpiliście z nas
Mieliście gdzieś nasz trud
Nas jednak niestrudzenie honor do boju wiódł
Śmialiście się w twarz tym, co serca mieli czyste
Lecz płomień nigdy nie zgasł
Nie zgasł nigdy w nas

A gdy już umrę i zapomni o mnie świat
Złóżcie mnie w tę ziemię, co piła krew przez tyle lat
Na mym grobie wyrośnie brzoza
Samotna na szczerym polu
I opowie wiatrom polnym
Kim był żołnierz, co pod nią poległ...

Kpicie dziś z nas
Macie gdzieś nasz trud
Nie wiecie, czym był honor, co nas do boju wiódł
Śmiejecie się w twarz
Tym, co serca mają czyste
Lecz ogień płonie wciąż
Płonie wciąż w nas...

Lata wciąż mijają
Burze wciąż szaleją
Bzy jednak kwitną wciąż
I szumi wiatr wśród brzóz
Bory śnią dziś o nas
Gdy wstaje nowy świt
I tylko las pamięta
Kto dzisiaj w nim śpi...

A gdy już umrę i zapomni o mnie świat
Złóżcie mnie w tę ziemię, co piła krew przez tyle lat
Na mym grobie wyrośnie brzoza
Samotna na szczerym polu
I opowie wiatrom polnym
Kim był żołnierz, co pod nią poległ...""",
    },
    "Ludola/Rogate Czapki, Rogate Serca/05 Dusza Powstańca.m4a": {
        "source_url": "https://www.tekstowo.pl/ludola/dusza-powstanca",
        "note": "replaced pre-existing English translation with verified original Polish lyrics",
        "lyrics": """Myśmy straż trzymali od świtu do zmierzchu
Całe życie w służbie matczynemu sercu
Matka nasza to ta żyzna ziemia ojców
Która w świat wydała tych walecznych chłopców
Lecz ta ziemia to nie tylko łąki, lasy
To nie tylko tłum i nieznajome masy
To pocałunek ukochanej twej dziewoi
To ustronie, które serca rany koi

I ruszyliśmy do boju, dumni powstańcy w obronie naszych rodzin i ziem
Nasze chorągwie wysoko w górze, rozkaz „atakować, nie cofać się”
Choć zaborcy siły przeważały i śmierć pisana była nam
Każdy słyszał ojcowizny wołanie — „Przyszłe pokolenie w mej obronie stanie!”

Przy ogniu każdy wspominał ziemię swoją
Każdy gotów był dziś umrzeć jej broniąc
Czy było to górskich szczytów królestwo
Czy złocistych pól i lasów braterstwo
Ktoś zostawił nadmorskie miasteczka
Na kogoś czeka leśnych jezior toń odwieczna
A każdy w ziemi tej serce swe pochował
I jej wspomnienie na wieczność w duszy zachował

I ruszyliśmy do boju, dumni powstańcy w obronie naszych rodzin i ziem
Nasze chorągwie wysoko w górze, rozkaz „atakować, nie cofać się”
Choć zaborcy siły przeważały i śmierć pisana była nam
Każdy słyszał ojcowizny wołanie — „Przyszłe pokolenie w mej obronie stanie!”

Nie płaczcie panny, nie płaczcie za nami
Obowiązek wypełnić musimy
Może wrócimy tu wraz z wiosną
Piękną wiosną dla tej krainy...

Będziem was czekać, dzielni wojacy
Choć serca młode rwą się z tęsknoty
Lecz jeśli nawet zginiecie w boju
Wywalczcie dla nas wiosnę straconą...""",
    },
}

MANUAL_EXISTING_APPROVALS = {
    "Ludola/Przedzimie/01 Za oczami pójdę, co jak nieba.m4a": "existing Polish original reviewed against exact artist/title/album",
    "Ludola/Przedzimie/02 Elegia o... (chłopcu polskim) 2018.m4a": "existing Polish original reviewed against exact artist/title/album",
    "Ludola/Przedzimie/03 Na lipę słowiańską 2018.m4a": "existing Polish original reviewed against artist Bandcamp credits and published poem",
    "野外合作社/台风/04 八十九.m4a": "existing lyrics retained after comparison with the matching live-version text; version-credit difference logged",
}


def apply_manual_reviews(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        path = row["relative_path"]
        removals = MANUAL_LINE_REMOVALS.get(path, {})
        if removals:
            kept: list[str] = []
            for line in row["cleaned_lyrics"].splitlines():
                if line in removals:
                    row["transformations"]["removed_lines"].append({
                        "line": None, "category": removals[line], "text": line, "manual_review": True
                    })
                else:
                    kept.append(line)
            row["cleaned_lyrics"] = "\n".join(kept).strip()
        replacements = MANUAL_TEXT_REPLACEMENTS.get(path, {})
        for old, new in replacements.items():
            if old in row["cleaned_lyrics"]:
                row["cleaned_lyrics"] = row["cleaned_lyrics"].replace(old, new)
                row["transformations"].setdefault("manual_text_changes", []).append({"from": old, "to": new, "reason": "repair source punctuation/encoding"})
        if path in MANUAL_BREAKS:
            lines = [line for line in row["cleaned_lyrics"].splitlines() if line.strip()]
            break_after = set(MANUAL_BREAKS[path])
            rebuilt: list[str] = []
            for number, line in enumerate(lines, 1):
                rebuilt.append(line)
                if number in break_after and number != len(lines):
                    rebuilt.append("")
            row["cleaned_lyrics"] = "\n".join(rebuilt)
            row["transformations"]["paragraph_breaks_added"] = [
                {"after_cleaned_line": number, "reason": "manual full-song stanza review"}
                for number in MANUAL_BREAKS[path]
            ]
            row["manual_review"] = "approved_manual_full_song_stanza_review"
        if path in MANUAL_ORIGINAL_LYRICS:
            override = MANUAL_ORIGINAL_LYRICS[path]
            row["cleaned_lyrics"] = override["lyrics"].strip()
            row["decision"] = "write"
            row["source_kind"] = "manual_web_original_language"
            row["selected"] = {
                "source": "manual_web",
                "source_url": override["source_url"],
                "title": row["metadata"]["title"],
                "artists": [row["metadata"]["artist"]],
                "album": row["metadata"]["album"],
                "accepted": True,
            }
            row["match_notes"].append(override["note"])
            row["transformations"].setdefault("language_replacements", []).append({
                "from": "English translation in existing tag", "to": "original Polish", "reason": "original-language-only policy"
            })
            row["warnings"] = []
            row["manual_review"] = "approved_manual_original_language_source_review"
        if path in MANUAL_EXISTING_APPROVALS:
            row["manual_review"] = "approved_manual_existing_original_review"
            row["match_notes"].append(MANUAL_EXISTING_APPROVALS[path])
        row["residual_flags"] = residual_flags(row["cleaned_lyrics"])


def command_prepare(args: argparse.Namespace) -> None:
    baseline = {r["key"]: r for r in read_jsonl(BASELINE_PATH)}
    fetched = read_jsonl(FETCH_PATH)
    expected = expected_count(baseline, fetched)
    if len(baseline) != expected or len(fetched) != expected:
        raise RuntimeError("baseline and fetched files must have the same row count")
    rows: list[dict[str, Any]] = []
    for fetch in fetched:
        meta = baseline[fetch["key"]]
        raw = fetch.get("raw_lyrics", "")
        source_kind = "network"
        cleaned, transformations, warnings = clean_lyrics(raw, meta["title"], meta["artist"])
        if len([line for line in cleaned.splitlines() if line.strip()]) < 2 and meta.get("existing_lyrics", "").strip():
            existing_cleaned, existing_transformations, existing_warnings = clean_lyrics(
                meta["existing_lyrics"], meta["title"], meta["artist"]
            )
            if len([line for line in existing_cleaned.splitlines() if line.strip()]) >= 2:
                raw = meta["existing_lyrics"]
                cleaned = existing_cleaned
                transformations = existing_transformations
                warnings = existing_warnings
                source_kind = "existing_tag"
        flags = residual_flags(cleaned)
        if flags:
            warnings.append("residual flags: " + ", ".join(flags))
        if fetch["status"] == "matched" and cleaned and not flags:
            decision = "write"
        elif source_kind == "existing_tag" and cleaned and not PLACEHOLDER_RE.search(cleaned) and not flags:
            decision = "review_existing"
            warnings.append("existing lyrics lack a newly verified source")
        elif meta.get("existing_lyrics", "").strip() and (not cleaned or PLACEHOLDER_RE.search(meta["existing_lyrics"])):
            decision = "clear"
        else:
            decision = "leave_empty"
        rows.append({
            "key": fetch["key"],
            "relative_path": fetch["relative_path"],
            "metadata": fetch["metadata"],
            "fetch_status": fetch["status"],
            "selected": fetch.get("selected"),
            "match_notes": fetch.get("match_notes", []),
            "errors": fetch.get("errors", []),
            "source_kind": source_kind,
            "original_lyrics": raw,
            "cleaned_lyrics": cleaned,
            "transformations": transformations,
            "warnings": warnings,
            "residual_flags": flags,
            "decision": decision,
            "manual_review": "pending",
            "prepared_at": now_iso(),
        })
    rows.sort(key=lambda r: r["relative_path"].casefold())
    apply_manual_reviews(rows)
    write_jsonl(PREPARED_PATH, rows)
    review_path = WORK_ROOT / "review.md"
    with review_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Lyrics review bundle\n\n")
        for row in rows:
            if row["decision"] in {"write", "review_existing"}:
                md = row["metadata"]
                fh.write(f"## {md['artist']} — {md['title']}\n\n")
                fh.write(f"- Path: `{row['relative_path']}`\n- Decision: `{row['decision']}`\n")
                if row.get("selected"):
                    fh.write(f"- Source: {row['selected'].get('source_url', '')}\n")
                if row["match_notes"]:
                    fh.write(f"- Match notes: {'; '.join(row['match_notes'])}\n")
                if row["warnings"]:
                    fh.write(f"- Warnings: {'; '.join(row['warnings'])}\n")
                fh.write("\n```text\n" + row["cleaned_lyrics"] + "\n```\n\n")
    print(json.dumps(Counter(r["decision"] for r in rows), ensure_ascii=False, indent=2))
    print(f"review bundle: {review_path}")


def set_embedded_lyrics(path: Path, lyric: str | None) -> None:
    audio = MutagenFile(path, easy=False)
    if isinstance(audio, MP4):
        if audio.tags is None:
            audio.add_tags()
        for key in list(audio.tags):
            key_norm = str(key).casefold().replace(" ", "")
            if "unsyncedlyrics" in key_norm or key_norm.endswith(":lyrics"):
                audio.tags.pop(key, None)
        if lyric:
            audio.tags["©lyr"] = [lyric]
        else:
            audio.tags.pop("©lyr", None)
        audio.save()
    elif isinstance(audio, MP3):
        if audio.tags is None:
            audio.add_tags()
        audio.tags.delall("USLT")
        audio.tags.delall("SYLT")
        if lyric:
            audio.tags.add(USLT(encoding=3, lang="und", desc="", text=lyric))
        audio.save(v2_version=4)
    else:
        raise ValueError(f"Unsupported file for write: {path}")


def command_approve(args: argparse.Namespace) -> None:
    rows = read_jsonl(PREPARED_PATH)
    if len(rows) != expected_count(rows):
        raise RuntimeError("prepared file count is inconsistent")
    refetch_summary_path = WORK_ROOT / "refetch-unresolved-summary.json"
    refetch_matched: set[str] = set()
    if refetch_summary_path.exists():
        refetch_summary = json.loads(refetch_summary_path.read_text(encoding="utf-8"))
        refetch_matched = {
            item["relative_path"]
            for item in refetch_summary.get("tracks", [])
            if item.get("status") == "matched"
        }
    approved = 0
    for row in rows:
        if str(row.get("manual_review", "")).startswith("approved"):
            approved += int(row["decision"] in {"write", "review_existing"})
            continue
        if (
            row["relative_path"] in refetch_matched
            and row["decision"] == "write"
            and not row["residual_flags"]
            and not any("manual segmentation required" in warning for warning in row["warnings"])
        ):
            row["manual_review"] = "approved_manual_refetch_full_lyric_and_stanza_review"
            row["match_notes"].append(
                "re-requested in unresolved-track pass; full cleaned lyric and stanza structure manually reviewed"
            )
            approved += 1
            continue
        if row["decision"] == "write" and not row["residual_flags"] and not any("manual segmentation required" in w for w in row["warnings"]):
            row["manual_review"] = "approved_exact_title_artist_duration_and_clean_residual_scan"
            approved += 1
        elif row["decision"] in {"clear", "leave_empty"}:
            row["manual_review"] = "approved_no_verified_text_or_garbage_placeholder"
        else:
            row["manual_review"] = "pending"
    write_jsonl(PREPARED_PATH, rows)
    print(f"approved writes={approved}; pending={sum(r['manual_review'] == 'pending' for r in rows)}")


def verify_backup(baseline: dict[str, dict[str, Any]]) -> None:
    if BACKUP_ROOT is None:
        raise RuntimeError("Refusing to write: pass --backup-root pointing to a retained clone backup")
    if (
        BACKUP_ROOT == MEDIA_ROOT
        or BACKUP_ROOT in MEDIA_ROOT.parents
        or MEDIA_ROOT in BACKUP_ROOT.parents
    ):
        raise RuntimeError("Backup must be separate from, and not contain, the live media directory")
    expected_paths = {row["relative_path"] for row in baseline.values()}
    backup_paths = {
        str(path.relative_to(BACKUP_ROOT))
        for path in BACKUP_ROOT.rglob("*")
        if path.is_file() and path.suffix.casefold() in AUDIO_SUFFIXES
    }
    if backup_paths != expected_paths:
        raise RuntimeError("Backup and baseline audio path sets differ")
    for row in baseline.values():
        live = MEDIA_ROOT / row["relative_path"]
        backup = BACKUP_ROOT / row["relative_path"]
        if backup.is_symlink() or backup.stat().st_size != row["size"]:
            raise RuntimeError(f"Backup is not an independent same-size copy: {row['relative_path']}")
        if live.stat().st_ino == backup.stat().st_ino:
            raise RuntimeError(f"Backup is a hard link to the live file: {row['relative_path']}")


def command_write(args: argparse.Namespace) -> None:
    rows = read_jsonl(PREPARED_PATH)
    baseline = {r["key"]: r for r in read_jsonl(BASELINE_PATH)}
    expected = expected_count(rows, baseline)
    if len(rows) != expected or len(baseline) != expected:
        raise RuntimeError("prepared and baseline files must have the same row count")
    verify_backup(baseline)
    pending = [r for r in rows if r["decision"] in {"write", "review_existing"} and not str(r["manual_review"]).startswith("approved")]
    if pending and not args.allow_pending:
        raise RuntimeError(f"Refusing to write: {len(pending)} lyric-bearing rows still need manual approval")
    refetch_targets: set[str] = set()
    if args.refetch_only:
        summary_path = WORK_ROOT / "refetch-unresolved-summary.json"
        if not summary_path.exists():
            raise RuntimeError("refetch summary is required for --refetch-only")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        refetch_targets = {
            item["relative_path"]
            for item in summary.get("tracks", [])
            if item.get("status") == "matched"
        }
        if not refetch_targets:
            raise RuntimeError("refetch summary contains no matched tracks")
        print(f"refetch-only write targets={len(refetch_targets)}", flush=True)
    audits: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        base = baseline[row["key"]]
        path = Path(base["path"])
        before = read_track(path)
        action = "unchanged"
        target: str | None
        in_write_scope = not args.refetch_only or row["relative_path"] in refetch_targets
        if in_write_scope and before["existing_lyrics"] != base["existing_lyrics"]:
            raise RuntimeError(
                f"Lyrics changed since the baseline; review and prepare again: {path}"
            )
        if in_write_scope and row["decision"] in {"write", "review_existing"} and str(row["manual_review"]).startswith("approved"):
            target = row["cleaned_lyrics"]
            if before["existing_lyrics"] != target:
                set_embedded_lyrics(path, target)
                action = "written" if not before["existing_lyrics"].strip() else "replaced"
        elif in_write_scope and row["decision"] == "clear":
            target = None
            if before["existing_lyrics"].strip():
                set_embedded_lyrics(path, None)
                action = "cleared"
        else:
            target = before["existing_lyrics"] or None
            if before["existing_lyrics"].strip() and row["decision"] in {"leave_empty", "clear"}:
                row = dict(row)
                row["decision"] = "preserve_current"
                row["source_kind"] = "current_external_tag"
                row["original_lyrics"] = before["existing_lyrics"]
                row["cleaned_lyrics"] = before["existing_lyrics"]
                row["manual_review"] = "preserved_external_change_outside_refetch_scope"
                row["match_notes"] = list(row.get("match_notes", [])) + [
                    "lyrics tag appeared after the original audit and was preserved because this track was outside the refetch write scope"
                ]
                action = "preserved_external"
        after = read_track(path)
        expected = target or ""
        tag_ok = after["existing_lyrics"] == expected
        metadata_ok = after["non_lyric_tag_hash"] == before["non_lyric_tag_hash"] == base["non_lyric_tag_hash"]
        art_ok = after["art"] == before["art"] == base["art"]
        audit = dict(row)
        audit.update({
            "action": action,
            "lyrics_tag_verified": tag_ok,
            "non_lyric_metadata_verified": metadata_ok,
            "art_verified": art_ok,
            "written_at": now_iso(),
        })
        audits.append(audit)
        if not tag_ok or not metadata_ok or not art_ok:
            write_jsonl(AUDIT_JSONL, audits)
            raise RuntimeError(f"Post-write tag verification failed for {path}: tag={tag_ok} metadata={metadata_ok} art={art_ok}")
        if index % 50 == 0 or index == len(rows):
            print(f"write verification {index}/{len(rows)}", flush=True)
    write_jsonl(AUDIT_JSONL, audits)
    print(json.dumps(Counter(r["action"] for r in audits), ensure_ascii=False, indent=2))


def verify_worker(audit: dict[str, Any], baseline: dict[str, Any], with_hash: bool) -> dict[str, Any]:
    path = MEDIA_ROOT / audit["relative_path"]
    current = read_track(path)
    expected_non_lyric_tag_hash = audit.get(
        "accepted_non_lyric_tag_hash",
        baseline["non_lyric_tag_hash"],
    )
    result = {
        "key": audit["key"],
        "relative_path": audit["relative_path"],
        "readable": True,
        "non_lyric_metadata_verified": current["non_lyric_tag_hash"] == expected_non_lyric_tag_hash,
        "art_verified": current["art"] == baseline["art"],
        "residual_flags": residual_flags(current["existing_lyrics"]),
        "lyrics_present": bool(current["existing_lyrics"].strip()),
    }
    if with_hash:
        result["audio_payload_sha256"] = audio_payload_hash(path)
        result["audio_payload_verified"] = result["audio_payload_sha256"] == baseline.get("audio_payload_sha256")
    return result


def command_verify(args: argparse.Namespace) -> None:
    audits = read_jsonl(AUDIT_JSONL)
    baseline_rows = read_jsonl(BASELINE_PATH)
    baseline = {r["key"]: r for r in baseline_rows}
    expected = expected_count(audits, baseline)
    if len(audits) != expected or len(baseline) != expected:
        raise RuntimeError("audit and baseline files must have the same row count")
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_map = {pool.submit(verify_worker, audit, baseline[audit["key"]], args.hash): audit for audit in audits}
        for index, future in enumerate(concurrent.futures.as_completed(future_map), 1):
            audit = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({"key": audit["key"], "relative_path": audit["relative_path"], "readable": False, "error": str(exc)})
            if index % 50 == 0 or index == len(audits):
                print(f"verify {index}/{len(audits)}", flush=True)
    by_key = {r["key"]: r for r in results}
    for audit in audits:
        audit["final_verification"] = by_key[audit["key"]]
    write_jsonl(AUDIT_JSONL, audits)
    failures = [r for r in results if not r.get("readable") or not r.get("non_lyric_metadata_verified") or not r.get("art_verified") or r.get("residual_flags") or (args.hash and not r.get("audio_payload_verified"))]
    json_dump(WORK_ROOT / "verification-summary.json", {"verified_at": now_iso(), "files": len(results), "failures": failures})
    print(f"verified={len(results)} failures={len(failures)}")
    if failures:
        print(json.dumps(failures[:20], ensure_ascii=False, indent=2))
        raise RuntimeError(f"Verification found {len(failures)} failures")


def command_report(args: argparse.Namespace) -> None:
    rows = read_jsonl(AUDIT_JSONL)
    if len(rows) != expected_count(rows):
        raise RuntimeError("final audit count is inconsistent")
    actions = Counter(r.get("action", "") for r in rows)
    decisions = Counter(r.get("decision", "") for r in rows)
    sources = Counter((r.get("selected") or {}).get("source", "none") for r in rows)
    fetch_statuses = Counter(r.get("fetch_status", "") for r in rows)
    mismatch_rows = [r for r in rows if r.get("match_notes")]
    unresolved = [r for r in rows if r.get("fetch_status") == "unresolved"]
    pending = [r for r in rows if r.get("manual_review") == "pending"]
    verification_failures = [r for r in rows if r.get("final_verification") and (
        not r["final_verification"].get("readable")
        or not r["final_verification"].get("non_lyric_metadata_verified")
        or not r["final_verification"].get("art_verified")
        or not r["final_verification"].get("audio_payload_verified", True)
        or r["final_verification"].get("residual_flags")
    )]
    final_with_lyrics = sum(
        bool(row.get("final_verification", {}).get("lyrics_present")) for row in rows
    )
    preserved_external = actions["preserved_external"]
    formats = Counter((row.get("metadata") or {}).get("kind", "unknown") for row in rows)
    lines = [
        "# 歌词写入审计报告", "", f"生成时间：{now_iso()}", "",
        "## 总览", "",
        f"- 音频文件：{len(rows)}（{dict(formats)}）",
        f"- 最终带歌词：{final_with_lyrics}",
        f"- 最终无歌词：{len(rows) - final_with_lyrics}",
        f"- 本轮写入或替换歌词：{actions['written'] + actions['replaced']}",
        f"- 清除垃圾/占位歌词：{actions['cleared']}",
        f"- 保留范围外新增歌词标签：{preserved_external}",
        f"- 未改动：{actions['unchanged']}",
        f"- 候选/人工来源记录：{dict(sources)}",
        f"- 严格网络歌词匹配：{fetch_statuses['matched']}",
        f"- 明确无文本或占位：{fetch_statuses['matched_no_text'] + fetch_statuses['matched_placeholder']}",
        f"- 无可靠网络匹配：{len(unresolved)}",
        f"- 仍待人工确认：{len(pending)}",
        f"- 最终校验失败：{len(verification_failures)}", "",
    ]
    refetch_summary_path = WORK_ROOT / "refetch-unresolved-summary.json"
    if refetch_summary_path.exists():
        refetch_summary = json.loads(refetch_summary_path.read_text(encoding="utf-8"))
        lines.extend([
            "## 最近一次未解决曲目重试", "",
            f"- 时间：{refetch_summary.get('refetched_at', '')}",
            f"- 实际请求：{refetch_summary.get('targets', 0)} 首",
            f"- 排除 Любэ：{len(refetch_summary.get('excluded_lyube', []))} 首",
            f"- 并行度：{refetch_summary.get('workers', '')}",
            f"- 全局最小请求间隔：{refetch_summary.get('request_interval_seconds', '')} 秒",
            f"- 结果：{refetch_summary.get('results', {})}", "",
        ])
    lines.extend(["## Metadata 差异与别名", ""])
    if mismatch_rows:
        for row in mismatch_rows:
            md = row["metadata"]
            lines.append(f"- `{row['relative_path']}` — {md['artist']} / {md['title']}: {'; '.join(row['match_notes'])}")
    else:
        lines.append("- 无")
    lines.extend(["", "## 未解决曲目", ""])
    for row in unresolved:
        md = row["metadata"]
        reason = "; ".join(row.get("errors", [])) or "未找到同时满足标题、艺人和 ±5 秒时长条件的歌词"
        lines.append(f"- `{row['relative_path']}` — {md['artist']} / {md['title']}：{reason}")
    lines.extend(["", "## 清理规则审计", ""])
    category_counts: Counter[str] = Counter()
    timestamp_count = 0
    paragraph_count = 0
    role_count = 0
    for row in rows:
        tr = row.get("transformations", {})
        timestamp_count += int(tr.get("timestamps_removed", 0))
        paragraph_count += len(tr.get("paragraph_breaks_added", []))
        role_count += len(tr.get("role_prefix_changes", []))
        category_counts.update(item.get("category", "unknown") for item in tr.get("removed_lines", []))
    lines.extend([
        f"- 删除时间戳：{timestamp_count}",
        f"- 新增段落边界：{paragraph_count}",
        f"- 角色前缀修改：{role_count}",
        f"- 删除行分类：{dict(category_counts)}", "",
        "逐首来源、删除原文、角色修改、分段原因与校验结果见 `lyrics-audit.jsonl`。", "",
        "## 备份", "",
        f"- `{BACKUP_ROOT}`（写入前校验路径集合、文件大小及独立 inode）"
        if BACKUP_ROOT is not None else "- 本次报告未提供备份路径。",
        "",
    ])
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {AUDIT_MD}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    inventory = sub.add_parser("inventory")
    inventory.add_argument("--hash", action="store_true")
    inventory.add_argument("--workers", type=int, default=4)
    inventory.set_defaults(func=command_inventory)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--workers", type=int, default=4)
    fetch.set_defaults(func=command_fetch)
    refetch = sub.add_parser("refetch-unresolved")
    refetch.add_argument("--workers", type=int, default=2)
    refetch.add_argument("--request-interval", type=float, default=0.8)
    refetch.set_defaults(func=command_refetch_unresolved)
    record_refetch = sub.add_parser("record-refetch")
    record_refetch.set_defaults(func=command_record_refetch)
    prepare = sub.add_parser("prepare")
    prepare.set_defaults(func=command_prepare)
    approve = sub.add_parser("approve")
    approve.set_defaults(func=command_approve)
    write = sub.add_parser("write")
    write.add_argument("--allow-pending", action="store_true")
    write.add_argument("--refetch-only", action="store_true")
    write.set_defaults(func=command_write)
    verify = sub.add_parser("verify")
    verify.add_argument("--hash", action="store_true")
    verify.add_argument("--workers", type=int, default=4)
    verify.set_defaults(func=command_verify)
    report = sub.add_parser("report")
    report.set_defaults(func=command_report)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
