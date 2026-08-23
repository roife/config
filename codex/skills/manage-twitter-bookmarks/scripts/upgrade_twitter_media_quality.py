#!/usr/bin/env python3
"""Replace archived Twitter/X videos with the highest available resolution.

The archive stays flat. yt-dlp downloads every video to temporary dot-files,
FFprobe validates them, and only then are the existing files atomically
replaced. Images are left untouched because the bookmark archiver already uses
pbs.twimg.com's `name=orig` variant.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Optional, Sequence, Tuple


MEDIA_ID_RE = re.compile(r"/(?:amplify_video|ext_tw_video)/(\d+)/")
REEXEC_GUARD = "TWITTER_HQ_REEXECUTED"


@dataclass(frozen=True)
class VideoTarget:
    media_id: str
    tweet_id: str
    tweet_url: str
    path: Path
    source_url: str


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="用 yt-dlp 将扁平化 Twitter/X 归档中的全部视频升级为可用的最高分辨率。"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("twitter-bookmarks"),
        help="只存放图片/视频的 target 目录（默认：./twitter-bookmarks）",
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        default=None,
        help="bookmarks.json 所在目录（默认：在 target 旁边加 -metadata）",
    )
    parser.add_argument(
        "--browser",
        choices=("arc", "chrome", "edge", "firefox", "brave"),
        default="chrome",
        help="读取 X 登录 Cookie 的浏览器（默认：chrome）",
    )
    parser.add_argument("--retries", type=int, default=5, help="下载重试次数（默认：5）")
    parser.add_argument("--fragments", type=int, default=4, help="HLS/DASH 分片并发数（默认：4）")
    parser.add_argument(
        "--keep-temporary",
        action="store_true",
        help="失败时保留 .hq-* 临时文件，便于人工检查",
    )
    args = parser.parse_args(argv)
    if args.retries < 0:
        parser.error("--retries 不能小于 0")
    if args.fragments <= 0:
        parser.error("--fragments 必须大于 0")
    return args


def atomic_write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(".%s.tmp-%d" % (path.name, os.getpid()))
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def executable_python(executable: str) -> Optional[str]:
    launcher = shutil.which(executable)
    if not launcher:
        return None
    try:
        first_line = Path(launcher).read_text(encoding="utf-8").splitlines()[0]
        command = shlex.split(first_line[2:].strip()) if first_line.startswith("#!") else []
    except (OSError, UnicodeError, IndexError, ValueError):
        return None
    if not command:
        return None
    if Path(command[0]).name == "env" and len(command) >= 2:
        return shutil.which(command[1])
    return command[0] if Path(command[0]).exists() else None


def ensure_runtime() -> Tuple[str, str]:
    yt_dlp = shutil.which("yt-dlp")
    ffprobe = shutil.which("ffprobe")
    if not yt_dlp:
        raise RuntimeError("找不到 yt-dlp；请先运行：uv tool install yt-dlp")
    if not ffprobe:
        raise RuntimeError("找不到 ffprobe；请先安装 FFmpeg")
    return yt_dlp, ffprobe


def safe_flat_target(root: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).name != relative_path:
        raise ValueError("媒体路径不是单目录文件名：%s" % relative_path)
    target = (root / relative_path).resolve()
    if target.parent != root:
        raise ValueError("媒体路径越界：%s" % relative_path)
    return target


def iter_tweet_nodes(data: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    yield data
    quoted = data.get("quotedTweet")
    if isinstance(quoted, dict):
        yield from iter_tweet_nodes(quoted)


def collect_targets(root: Path, records: List[Any]) -> Tuple[DefaultDict[str, List[VideoTarget]], List[str]]:
    targets: DefaultDict[str, List[VideoTarget]] = defaultdict(list)
    tweet_urls: Dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        for node in iter_tweet_nodes(record):
            tweet_id = str(node.get("id") or "")
            tweet_url = str(node.get("permalink") or ("https://x.com/i/status/%s" % tweet_id))
            node_has_video = False
            for media in node.get("media") or []:
                if not isinstance(media, dict) or media.get("type") not in {"video", "animated_gif"}:
                    continue
                source_url = str(media.get("downloadUrl") or media.get("url") or "")
                match = MEDIA_ID_RE.search(source_url)
                if not match:
                    raise ValueError("无法从视频 URL 提取媒体 ID：%s" % source_url)
                relative_path = str(media.get("localPath") or "")
                media_id = match.group(1)
                targets[media_id].append(
                    VideoTarget(
                        media_id=media_id,
                        tweet_id=tweet_id,
                        tweet_url=tweet_url,
                        path=safe_flat_target(root, relative_path),
                        source_url=source_url,
                    )
                )
                node_has_video = True
            if node_has_video and tweet_id and tweet_id not in tweet_urls:
                tweet_urls[tweet_id] = tweet_url
    return targets, list(tweet_urls.values())


def probe_video(ffprobe: str, path: Path) -> Dict[str, Any]:
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,codec_name,bit_rate:format=duration,size,bit_rate",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "FFprobe 无法读取视频")
    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    if not streams:
        raise ValueError("文件中没有视频流")
    stream = streams[0]
    format_data = payload.get("format") or {}
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    size = int(format_data.get("size") or path.stat().st_size)
    duration = float(format_data.get("duration") or 0)
    bitrate = int(stream.get("bit_rate") or format_data.get("bit_rate") or 0)
    if width <= 0 or height <= 0 or size <= 0 or duration <= 0:
        raise ValueError("视频流参数无效")
    return {
        "width": width,
        "height": height,
        "duration": duration,
        "size": size,
        "bitrate": bitrate,
        "codec": stream.get("codec_name") or "",
    }


def temporary_candidates(root: Path, media_id: str) -> List[Path]:
    blocked_suffixes = {".part", ".ytdl", ".json", ".vtt", ".srt"}
    return [
        path
        for path in root.glob(".hq-%s.*" % media_id)
        if path.is_file() and path.suffix.lower() not in blocked_suffixes and ".f" not in path.stem[-8:]
    ]


def pick_valid_candidate(ffprobe: str, root: Path, media_id: str) -> Tuple[Path, Dict[str, Any]]:
    valid: List[Tuple[int, int, Path, Dict[str, Any]]] = []
    errors: List[str] = []
    for path in temporary_candidates(root, media_id):
        try:
            info = probe_video(ffprobe, path)
            valid.append((info["width"] * info["height"], info["bitrate"], path, info))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append("%s: %s" % (path.name, exc))
    if not valid:
        message = "; ".join(errors) if errors else "yt-dlp 没有生成对应文件"
        raise ValueError(message)
    _, _, path, info = max(valid, key=lambda item: (item[0], item[1], item[3]["size"]))
    return path, info


def replace_targets(candidate: Path, targets: List[VideoTarget]) -> None:
    for target in targets:
        replacement = target.path.with_name(".%s.hq-replacement-%d" % (target.path.name, os.getpid()))
        try:
            shutil.copy2(candidate, replacement)
            os.replace(replacement, target.path)
        finally:
            try:
                replacement.unlink()
            except FileNotFoundError:
                pass


def cleanup_temporary(root: Path) -> int:
    removed = 0
    for path in root.glob(".hq-*"):
        if path.is_file():
            path.unlink()
            removed += 1
    return removed


def run_ytdlp(
    yt_dlp: str,
    root: Path,
    browser: str,
    retries: int,
    fragments: int,
    tweet_urls: List[str],
) -> int:
    output_template = str(root / ".hq-%(id)s.%(ext)s")
    command = [
        yt_dlp,
        "--cookies-from-browser",
        browser,
        "--format",
        "bestvideo*+bestaudio/best",
        "--format-sort",
        "res,br",
        "--merge-output-format",
        "mp4",
        "--remux-video",
        "mp4",
        "--output",
        output_template,
        "--continue",
        "--no-overwrites",
        "--ignore-errors",
        "--retries",
        str(retries),
        "--fragment-retries",
        str(retries),
        "--concurrent-fragments",
        str(fragments),
        "--newline",
        "--progress-template",
        "download:%(info.id)s %(progress._percent_str)s %(progress._speed_str)s ETA %(progress._eta_str)s",
        "--print",
        "after_move:SELECTED %(id)s %(width)sx%(height)s %(format_id)s %(filepath)s",
        *tweet_urls,
    ]
    print("将检查 %d 个含视频的推文节点……" % len(tweet_urls), flush=True)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        print(line.rstrip(), flush=True)
    return process.wait()


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    root = args.output.expanduser().resolve()
    metadata_root = (
        args.metadata_output.expanduser().resolve()
        if args.metadata_output is not None
        else root.with_name(root.name + "-metadata")
    )
    if root == metadata_root or root in metadata_root.parents or metadata_root in root.parents:
        print("错误：媒体 target 与 metadata 目录必须彼此分离，且不能互相嵌套。", file=sys.stderr)
        return 1
    bookmarks_path = metadata_root / "bookmarks.json"
    if not bookmarks_path.is_file():
        print("错误：找不到 %s" % bookmarks_path, file=sys.stderr)
        return 1

    try:
        yt_dlp, ffprobe = ensure_runtime()
        records = json.loads(bookmarks_path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("bookmarks.json 顶层不是数组")
        targets, tweet_urls = collect_targets(root, records)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print("错误：%s" % exc, file=sys.stderr)
        return 1

    print(
        "发现 %d 个视频引用、%d 个唯一媒体 ID；图片保持原始尺寸。"
        % (sum(len(values) for values in targets.values()), len(targets)),
        flush=True,
    )
    yt_dlp_status = run_ytdlp(yt_dlp, root, args.browser, args.retries, args.fragments, tweet_urls)

    report: Dict[str, Any] = {
        "schemaVersion": 1,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "mode": "highest-resolution-available-from-x",
        "videoReferences": sum(len(values) for values in targets.values()),
        "uniqueMedia": len(targets),
        "ytDlpExitCode": yt_dlp_status,
        "items": [],
    }
    failures = 0
    replaced = 0
    for index, (media_id, media_targets) in enumerate(targets.items(), start=1):
        item: Dict[str, Any] = {
            "mediaId": media_id,
            "targets": [target.path.name for target in media_targets],
        }
        try:
            candidate, info = pick_valid_candidate(ffprobe, root, media_id)
            replace_targets(candidate, media_targets)
            for target in media_targets:
                confirmed = probe_video(ffprobe, target.path)
                if confirmed["width"] != info["width"] or confirmed["height"] != info["height"]:
                    raise ValueError("替换后分辨率验证不一致")
            item.update({"status": "replaced", **info})
            replaced += len(media_targets)
            print(
                "[%d/%d] %s：%dx%d，已替换 %d 个文件"
                % (index, len(targets), media_id, info["width"], info["height"], len(media_targets)),
                flush=True,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failures += len(media_targets)
            item.update({"status": "failed", "error": str(exc)})
            print("[%d/%d] %s：失败 — %s" % (index, len(targets), media_id, exc), flush=True)
        report["items"].append(item)

    report["replacedReferences"] = replaced
    report["failedReferences"] = failures
    report["complete"] = failures == 0
    metadata_root.mkdir(parents=True, exist_ok=True)
    atomic_write_json(metadata_root / "highest-resolution-report.json", report)

    manifest_path = metadata_root / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(manifest, dict):
                manifest["quality"] = {
                    "mode": report["mode"],
                    "updatedAt": report["updatedAt"],
                    "videoReferences": report["videoReferences"],
                    "replacedReferences": replaced,
                    "failedReferences": failures,
                    "complete": failures == 0,
                }
                atomic_write_json(manifest_path, manifest)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print("警告：无法更新 manifest.json：%s" % exc, file=sys.stderr)

    if failures == 0 or not args.keep_temporary:
        removed = cleanup_temporary(root)
        print("已清理 %d 个临时文件。" % removed, flush=True)
    print("最高分辨率升级：成功 %d，失败 %d。" % (replaced, failures), flush=True)
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
