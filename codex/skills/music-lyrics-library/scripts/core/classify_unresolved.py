#!/usr/bin/env python3
"""Split the current lyric-less audit entries into conservative review lists."""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path


ROOT = Path("/Users/roifewu/Music")
MEDIA_ROOT = ROOT / "Music/Media.localized/Music"
AUDIT_PATH = ROOT / "lyrics-audit.jsonl"
INSTRUMENTAL_REPORT = ROOT / "纯音乐曲目.md"
UNRESOLVED_REPORT = ROOT / "未解决曲目.md"

LIVE_PATH_OVERRIDES = {
    "Glow Curve/Glow Curve/04 The Gate of Tiananless.m4a": (
        "发光曲线/发光曲线/04 The Gate of Tiananless.m4a"
    ),
    "Compilations/Spasibo Dedu Za Pobedu!/11 Cvety Na Belom Platie.m4a": (
        "Compilations/Спасибо Деду За Победу!/11 Цветы На Белом Платье.m4a"
    ),
}


# These artists occur in the lyric-less set only as film-score or instrumental
# post-rock recordings. The exact album/recording context is retained in each
# output row so the classification remains auditable.
INSTRUMENTAL_ARTIST_REASONS = {
    "阿鲲": "电影配乐专辑；同专辑的精确匹配结果均为纯音乐占位",
    "Hans Zimmer": "电影配乐专辑；精确匹配结果为纯音乐占位",
    "Ludwig Göransson": "电影配乐专辑；全套精确匹配结果为纯音乐占位",
    "Peyman Yazdanian": "电影配乐曲目；同专辑精确匹配结果为纯音乐占位",
    "Philippe Rombi": "电影配乐主题曲；精确匹配结果为纯音乐占位",
    "坂本龍一": "电影配乐/器乐主题曲；精确匹配结果为纯音乐占位",
    "Abigail Mead, Nigel Goulding": "电影原声主题配乐",
    "P.T. Adamczyk": "游戏原声配乐；精确匹配仅有作曲信息、无歌词正文",
    "pg.lost": "器乐后摇作品；同版本匹配无歌词正文",
    "Wang Wen": "惘闻的英文艺人名；器乐后摇作品",
    "惘闻": "器乐后摇作品；同艺人/专辑大量精确匹配结果为纯音乐占位",
}


def load_lyricless_rows() -> list[dict]:
    rows = [json.loads(line) for line in AUDIT_PATH.open(encoding="utf-8")]
    return [
        row
        for row in rows
        if not row.get("final_verification", {}).get("lyrics_present", False)
    ]


def classify(row: dict) -> tuple[str, str]:
    if row.get("fetch_status") == "user_confirmed_no_lyrics":
        return "instrumental", "用户明确确认该录音没有歌词正文"
    if row.get("fetch_status") == "matched_instrumental":
        return "instrumental", "已人工核对匹配资料，曲目标明为器乐演奏"
    metadata = row["metadata"]
    if row.get("fetch_status") == "matched_placeholder":
        return "instrumental", "同标题、艺人、时长版本匹配，来源仅返回纯音乐占位"

    artist = metadata.get("artist", "")
    if artist in INSTRUMENTAL_ARTIST_REASONS:
        return "instrumental", INSTRUMENTAL_ARTIST_REASONS[artist]

    if row.get("fetch_status") == "matched_no_text":
        return "unresolved", "同版本来源无可用正文；空响应不能证明是纯音乐"
    return "unresolved", "尚无可靠歌词匹配，且没有充分证据判定为纯音乐"


def link_for(row: dict) -> str:
    relative_path = row["relative_path"]
    path = MEDIA_ROOT / LIVE_PATH_OVERRIDES.get(relative_path, relative_path)
    return f"[音频](<{path}>)"


def duration_text(seconds: float) -> str:
    total = round(seconds)
    return f"{total // 60}:{total % 60:02d}"


def group_rows(rows: list[tuple[dict, str]]) -> OrderedDict[tuple[str, str], list]:
    groups: OrderedDict[tuple[str, str], list] = OrderedDict()
    for row, reason in sorted(
        rows,
        key=lambda item: (
            item[0]["metadata"].get("artist", "").casefold(),
            item[0]["metadata"].get("album", "").casefold(),
            item[0]["relative_path"].casefold(),
        ),
    ):
        metadata = row["metadata"]
        key = (metadata.get("artist", "") or "（艺人缺失）", metadata.get("album", "") or "（专辑缺失）")
        groups.setdefault(key, []).append((row, reason))
    return groups


def render_report(
    *,
    title: str,
    intro: str,
    rows: list[tuple[dict, str]],
    total_lyricless: int,
) -> str:
    lines = [
        f"# {title}",
        "",
        f"生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        intro,
        "",
        f"- 本列表：{len(rows)} 首",
        f"- 本轮最终无歌词曲目总数：{total_lyricless} 首",
        "- 范围：仅包含当前审计中写回后仍无歌词的文件",
        "",
    ]

    for (artist, album), items in group_rows(rows).items():
        lines.extend([f"## {artist} — {album}（{len(items)} 首）", ""])
        for row, reason in items:
            metadata = row["metadata"]
            title_text = metadata.get("title", "") or "（标题缺失）"
            duration = duration_text(float(metadata.get("duration", 0)))
            lines.append(f"- {title_text}（{duration}）— {reason} — {link_for(row)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    lyricless = load_lyricless_rows()
    instrumental: list[tuple[dict, str]] = []
    unresolved: list[tuple[dict, str]] = []

    for row in lyricless:
        category, reason = classify(row)
        target = instrumental if category == "instrumental" else unresolved
        target.append((row, reason))

    INSTRUMENTAL_REPORT.write_text(
        render_report(
            title="纯音乐曲目",
            intro=(
                "以下曲目已有较强证据表明没有可写入的歌词正文。判断采用保守口径："
                "用户明确确认无歌词、精确版本明确返回纯音乐占位，或作品属于已核对的"
                "电影配乐/器乐后摇专辑。"
            ),
            rows=instrumental,
            total_lyricless=len(lyricless),
        ),
        encoding="utf-8",
    )
    UNRESOLVED_REPORT.write_text(
        render_report(
            title="未解决曲目",
            intro=(
                "以下曲目不能判定为纯音乐，或明确属于有演唱/朗诵但尚未取得可靠歌词。"
                "同版本歌词接口返回空白也保留在此列表，因为空响应本身不能证明曲目无歌词。"
            ),
            rows=unresolved,
            total_lyricless=len(lyricless),
        ),
        encoding="utf-8",
    )

    assert len(instrumental) + len(unresolved) == len(lyricless)
    print(
        json.dumps(
            {
                "lyricless": len(lyricless),
                "instrumental": len(instrumental),
                "unresolved": len(unresolved),
                "instrumental_report": str(INSTRUMENTAL_REPORT),
                "unresolved_report": str(UNRESOLVED_REPORT),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
