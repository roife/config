#!/usr/bin/env python3
"""Generate a two-line local/NetEase comparison list for unresolved tracks."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from classify_unresolved import classify
from mutagen.mp4 import MP4
from mutagen.mp3 import MP3


ROOT = Path(os.environ.get("LYRICS_LIBRARY_ROOT", Path.cwd())).expanduser().resolve()
AUDIT_PATH = ROOT / "lyrics-audit.jsonl"
FETCHED_PATH = ROOT / ".lyrics-work/fetched.jsonl"
OUTPUT_PATH = ROOT / "网易云近似候选-未解决曲目.md"
MEDIA_ROOT = ROOT / "Music/Media.localized/Music"


# These candidates were recovered with artist aliases or the matching NetEase
# album track list after the original title+artist search ranked them poorly.
MANUAL_CANDIDATES: dict[str, dict[str, Any]] = {
    "Glow Curve/Glow Curve/01 Song for Raying Temple.m4a": {
        "source_id": "356752", "title": "小雷音之歌", "artists": ["发光曲线"],
        "album": "发光曲线", "duration": 430.0,
        "manual_note": "艺人别名、同专辑及近乎相同时长定位",
    },
    "Glow Curve/Glow Curve/02 Flowers of Godmother.m4a": {
        "source_id": "356754", "title": "鲜花圣母", "artists": ["发光曲线"],
        "album": "发光曲线", "duration": 545.567,
        "manual_note": "艺人别名、同专辑及近乎相同时长定位",
    },
    "Glow Curve/Glow Curve/03 Kindergarten.m4a": {
        "source_id": "356756", "title": "幼儿园", "artists": ["发光曲线"],
        "album": "发光曲线", "duration": 398.0,
        "manual_note": "艺人别名、同专辑及近乎相同时长定位",
    },
    "Glow Curve/Glow Curve/05 Died in the Rotating Apartment.m4a": {
        "source_id": "356760", "title": "死在旋转公寓", "artists": ["发光曲线"],
        "album": "发光曲线", "duration": 453.746,
        "manual_note": "艺人别名、同专辑及近乎相同时长定位",
    },
    "Glow Curve/Glow Curve/06 Floaing Mountains.m4a": {
        "source_id": "356762", "title": "浮山", "artists": ["发光曲线"],
        "album": "发光曲线", "duration": 608.0,
        "manual_note": "艺人别名、同专辑及近乎相同时长定位",
    },
    "腰/他们说忘了摇滚有问题 (Forget Rock N Roll, We've Got a Problem)/1-01 你一定听到了.m4a": {
        "source_id": "1386737245", "title": "你一定听到了", "artists": ["腰乐队"],
        "album": "他们说忘了摇滚有问题", "duration": 95.5,
        "manual_note": "用网易云艺人名“腰乐队”重新搜索后定位",
    },
}


# Explicit user decisions: omit these from the comparison sheet without
# claiming that the tracks are instrumental or otherwise changing their audit
# classification.
MANUAL_EXCLUSIONS: dict[str, str] = {
    "Compilations/流浪地球 电影原声大碟/34 让我们点燃木星.m4a": "用户要求从网易云近似候选中移除",
    "野外合作社/台风/07 上帝的意志.m4a": "用户要求从网易云近似候选中移除",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(ch for ch in value if ch.isalnum())


ARTIST_ALIASES = {
    "glowcurve": "发光曲线",
    "发光曲线": "发光曲线",
    "腰": "腰",
    "腰乐队": "腰",
    "shigeokomori": "小森茂生",
    "小森茂生": "小森茂生",
    "taiseiiwasaki": "岩崎太整",
    "岩崎太整": "岩崎太整",
    "老王乐队": "老王乐队",
    "老王樂隊": "老王乐队",
    "哪吒": "哪吒",
    "哪吒乐队": "哪吒",
    "哪吒樂隊": "哪吒",
}


def artist_tokens(value: str) -> set[str]:
    pieces = re.split(
        r"\s*(?:,|，|、|&|／|/|;|；|\bfeat(?:uring)?\.?\b|\bft\.?\b|\band\b)\s*",
        value,
        flags=re.I,
    )
    result: set[str] = set()
    for piece in pieces:
        token = normalized(piece)
        token = re.sub(r"(?:乐队|樂隊|band)$", "", token)
        if token:
            result.add(ARTIST_ALIASES.get(token, token))
    return result


def same_artist(metadata_artist: str, candidate: dict[str, Any]) -> bool:
    if candidate.get("artist_match") is True:
        return True
    local = artist_tokens(metadata_artist)
    remote: set[str] = set()
    for artist in candidate.get("artists") or []:
        remote.update(artist_tokens(str(artist)))
    return bool(local & remote)


def is_lyube(artist: str) -> bool:
    value = normalized(artist)
    return value.startswith("любэ") or value.startswith("любе")


def is_anthemics(artist: str) -> bool:
    return normalized(artist) == "anthemics"


def has_embedded_lyrics(path: Path) -> bool:
    if path.suffix.casefold() == ".m4a":
        tags = MP4(path).tags or {}
        return any(str(value).strip() for value in tags.get("\xa9lyr", []))
    if path.suffix.casefold() == ".mp3":
        tags = MP3(path).tags
        return bool(tags and any(str(frame.text).strip() for frame in tags.getall("USLT")))
    return False


def resolve_media_path(relative_path: str, paths_by_name: dict[str, list[Path]]) -> Path:
    expected = MEDIA_ROOT / relative_path
    if expected.exists():
        return expected
    if expected.parent.exists():
        track_prefix = expected.name.split(" ", 1)[0]
        same_track = [
            path for path in expected.parent.iterdir()
            if path.is_file()
            and path.suffix.casefold() == expected.suffix.casefold()
            and path.name.split(" ", 1)[0] == track_prefix
        ]
        if len(same_track) == 1:
            return same_track[0]
    candidates = paths_by_name.get(expected.name, [])
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"cannot uniquely resolve current media path for {relative_path}")


def format_duration(seconds: float) -> str:
    rounded = int(round(seconds))
    return f"{rounded // 60}:{rounded % 60:02d} ({seconds:.3f}s)"


def candidate_rank(candidate: dict[str, Any], metadata: dict[str, Any]) -> tuple[float, ...]:
    title_similarity = SequenceMatcher(
        None, normalized(metadata.get("title", "")), normalized(candidate.get("title", ""))
    ).ratio()
    artist_text = " / ".join(candidate.get("artists") or [])
    artist_similarity = SequenceMatcher(
        None, normalized(metadata.get("artist", "")), normalized(artist_text)
    ).ratio()
    album_similarity = SequenceMatcher(
        None, normalized(metadata.get("album", "")), normalized(candidate.get("album", ""))
    ).ratio()
    duration_difference = abs(float(metadata.get("duration") or 0) - float(candidate.get("duration") or 0))
    return (
        float(candidate.get("score") or 0),
        title_similarity,
        artist_similarity,
        album_similarity,
        -duration_difference,
    )


def best_netease_candidate(fetch: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any] | None:
    selected = fetch.get("selected")
    if selected and selected.get("source") == "netease" and same_artist(metadata.get("artist", ""), selected):
        return dict(selected)
    candidates = [
        item for item in (fetch.get("candidates") or [])
        if item.get("source") == "netease" and same_artist(metadata.get("artist", ""), item)
    ]
    if not candidates:
        return None
    return dict(max(candidates, key=lambda item: candidate_rank(item, metadata)))


def comparison_note(metadata: dict[str, Any], candidate: dict[str, Any], fetch: dict[str, Any]) -> str:
    differences: list[str] = []
    if not candidate.get("title_match", normalized(metadata["title"]) == normalized(candidate["title"])):
        differences.append("标题不同")
    if candidate.get("artist_match") is not True and same_artist(metadata.get("artist", ""), candidate):
        differences.append("艺人语言或署名别名")
    if not candidate.get("album_match", normalized(metadata.get("album", "")) == normalized(candidate.get("album", ""))):
        differences.append("专辑不同")
    duration_difference = abs(float(metadata.get("duration") or 0) - float(candidate.get("duration") or 0))
    if duration_difference <= 5.0:
        differences.append(f"时长近似（差 {duration_difference:.3f}s）")
    else:
        differences.append(f"时长差 {duration_difference:.3f}s")
    if candidate.get("manual_note"):
        differences.append(candidate["manual_note"])
    if fetch.get("status") == "matched_no_text" and fetch.get("selected", {}).get("source") == "netease":
        differences.append("元数据已匹配，但网易云歌词为空或仅有占位内容")
    score = candidate.get("score")
    if score is not None and score < 100:
        differences.append("低相关搜索结果")
    return "；".join(differences)


def main() -> None:
    audits = read_jsonl(AUDIT_PATH)
    fetched = {row["key"]: row for row in read_jsonl(FETCHED_PATH)}
    current_audio = [
        path for path in MEDIA_ROOT.rglob("*")
        if path.is_file() and path.suffix.casefold() in {".m4a", ".mp3"}
    ]
    paths_by_name: dict[str, list[Path]] = defaultdict(list)
    for path in current_audio:
        paths_by_name[path.name].append(path)
    resolved_paths: dict[str, Path] = {}
    targets: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]] = []
    unresolved_non_lyube = 0
    excluded_with_live_lyrics: list[str] = []
    excluded_anthemics: list[str] = []
    excluded_by_user: list[str] = []

    for audit in audits:
        if audit.get("final_verification", {}).get("lyrics_present", False):
            continue
        category, _ = classify(audit)
        metadata = audit["metadata"]
        if category != "unresolved" or is_lyube(metadata.get("artist", "")):
            continue
        unresolved_non_lyube += 1
        if is_anthemics(metadata.get("artist", "")):
            excluded_anthemics.append(audit["relative_path"])
            continue
        if audit["relative_path"] in MANUAL_EXCLUSIONS:
            excluded_by_user.append(audit["relative_path"])
            continue
        media_path = resolve_media_path(audit["relative_path"], paths_by_name)
        resolved_paths[audit["key"]] = media_path
        if has_embedded_lyrics(media_path):
            excluded_with_live_lyrics.append(audit["relative_path"])
            continue
        fetch = fetched[audit["key"]]
        candidate = MANUAL_CANDIDATES.get(audit["relative_path"])
        if candidate:
            candidate = dict(candidate)
            candidate.update({
                "source": "netease",
                "source_url": f"https://music.163.com/song?id={candidate['source_id']}",
                "title_match": normalized(metadata["title"]) == normalized(candidate["title"]),
                "artist_match": True,
                "album_match": True,
            })
        else:
            candidate = best_netease_candidate(fetch, metadata)
        targets.append((audit, fetch, candidate))

    targets.sort(key=lambda item: item[0]["relative_path"].casefold())
    # The unresolved total changes whenever the user adds lyrics or confirms a
    # match, so only assert that the current partition is internally complete.
    assert (
        len(targets)
        + len(excluded_with_live_lyrics)
        + len(excluded_anthemics)
        + len(excluded_by_user)
        == unresolved_non_lyube
    )

    counts = Counter("有候选" if candidate else "无候选" for _, _, candidate in targets)
    lines = [
        "# 未解决曲目的网易云同艺人近似候选（不含 Любэ、Anthemics）",
        "",
        f"- 原审计中的未解决且非 Любэ 曲目：{unresolved_non_lyube} 首",
        f"- 已检测到当前内嵌歌词并移出列表：{len(excluded_with_live_lyrics)} 首",
        f"- 按要求排除 Anthemics：{len(excluded_anthemics)} 首",
        f"- 按用户指定曲目排除：{len(excluded_by_user)} 首",
        f"- 当前列表：{len(targets)} 首",
        f"- 找到网易云同艺人候选：{counts['有候选']} 首",
        f"- 未找到网易云同艺人候选：{counts['无候选']} 首",
        "- 每项固定两行：第一行是本地 metadata，第二行是网易云候选。候选只用于人工判断，尚未据此写入歌词。",
        "",
    ]

    for audit, fetch, candidate in targets:
        metadata = audit["metadata"]
        local_path = resolved_paths[audit["key"]]
        current_relative_path = str(local_path.relative_to(MEDIA_ROOT))
        lines.append(
            f"- 本地：[《{metadata['title']}》](<{local_path}>) — {metadata.get('artist') or '（艺人缺失）'}；"
            f"《{metadata.get('album') or '（专辑缺失）'}》；{format_duration(float(metadata.get('duration') or 0))}；"
            f"路径 `{current_relative_path}`"
        )
        if candidate:
            artists = " / ".join(candidate.get("artists") or []) or "（艺人缺失）"
            note = comparison_note(metadata, candidate, fetch)
            lines.append(
                f"  网易云：[《{candidate.get('title') or '（标题缺失）'}》]({candidate['source_url']}) — {artists}；"
                f"《{candidate.get('album') or '（专辑缺失）'}》；{format_duration(float(candidate.get('duration') or 0))}；"
                f"ID `{candidate.get('source_id', '')}`；{note}"
            )
        else:
            lines.append("  网易云：未找到同艺人候选。")
        lines.append("")

    OUTPUT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(dict(counts))
    print(f"excluded live lyrics: {len(excluded_with_live_lyrics)}")
    for relative_path in excluded_with_live_lyrics:
        print(f"  {relative_path}")


if __name__ == "__main__":
    main()
