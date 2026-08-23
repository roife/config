#!/usr/bin/env python3
"""Remove every Twitter/X bookmark after verifying a local archive exists."""

from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


LOG = logging.getLogger("clear-twitter-bookmarks")
REEXEC_GUARD = "TWITTER_CLEAR_BOOKMARKS_REEXECUTED"


def twitter_cli_python() -> Optional[str]:
    launcher = shutil.which("twitter")
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


def load_twitter_cli() -> Tuple[Any, Any, Any, Any, str]:
    try:
        import twitter_cli
        from twitter_cli.auth import get_cookies
        from twitter_cli.client import TwitterClient
        from twitter_cli.config import load_config
        from twitter_cli.serialization import tweet_to_dict

        return get_cookies, TwitterClient, load_config, tweet_to_dict, getattr(twitter_cli, "__version__", "unknown")
    except ImportError as exc:
        interpreter = twitter_cli_python()
        already_reexecuted = os.environ.get(REEXEC_GUARD) == "1"
        if interpreter and not already_reexecuted and Path(interpreter).resolve() != Path(sys.executable).resolve():
            env = os.environ.copy()
            env[REEXEC_GUARD] = "1"
            os.execve(interpreter, [interpreter, str(Path(__file__).resolve()), *sys.argv[1:]], env)
        raise RuntimeError("找不到 twitter-cli；请确认 `twitter --version` 可以运行。") from exc


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="核对本地归档后，取消当前账号的全部 Twitter/X bookmarks。")
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("twitter-bookmarks-metadata"),
        help="本地归档元数据目录（默认：./twitter-bookmarks-metadata）",
    )
    parser.add_argument(
        "--max-bookmarks",
        type=int,
        default=100_000,
        help="读取当前 bookmarks 的安全上限（默认：100000）",
    )
    parser.add_argument(
        "--allow-unarchived",
        action="store_true",
        help="即使发现不在本地归档中的 bookmark 也继续删除",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="显示调试日志")
    args = parser.parse_args(argv)
    if args.max_bookmarks <= 0:
        parser.error("--max-bookmarks 必须大于 0")
    return args


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp-%d" % (path.name, os.getpid()))
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def iter_tweet_nodes(data: Dict[str, Any]) -> Sequence[Dict[str, Any]]:
    nodes = [data]
    quoted = data.get("quotedTweet")
    if isinstance(quoted, dict):
        nodes.extend(iter_tweet_nodes(quoted))
    return nodes


def validate_archive(metadata: Path) -> Tuple[List[Any], set[str]]:
    """Refuse destructive work unless metadata and every media file are complete."""
    archive_path = metadata / "bookmarks.json"
    manifest_path = metadata / "manifest.json"
    if not archive_path.is_file() or not manifest_path.is_file():
        raise ValueError("缺少 bookmarks.json 或 manifest.json；请重新运行完整归档流程")

    archived = json.loads(archive_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(archived, list) or not isinstance(manifest, dict):
        raise ValueError("归档 JSON 结构无效")
    if manifest.get("complete") is not True:
        raise ValueError("manifest.json 未标记 complete: true")
    if manifest.get("bookmarkFetchComplete") is not True:
        raise ValueError("bookmark 游标遍历未完成")
    if manifest.get("mediaComplete") is not True or manifest.get("mediaFailed") != 0:
        raise ValueError("媒体归档不完整或存在下载失败")
    if manifest.get("layout") != "flat":
        raise ValueError("归档不是受支持的 flat 布局")
    if manifest.get("bookmarkCount") != len(archived):
        raise ValueError("manifest 的 bookmarkCount 与 bookmarks.json 不一致")

    archived_ids = {
        str(item.get("id"))
        for item in archived
        if isinstance(item, dict) and item.get("id")
    }
    if len(archived_ids) != len(archived):
        raise ValueError("bookmarks.json 含缺失或重复的 bookmark ID")

    media_root_value = manifest.get("mediaRoot")
    if not isinstance(media_root_value, str) or not media_root_value:
        raise ValueError("manifest 缺少 mediaRoot；请用新版归档脚本重跑")
    media_root = (metadata / media_root_value).resolve()
    if media_root == metadata or media_root in metadata.parents or metadata in media_root.parents:
        raise ValueError("mediaRoot 与 metadata 目录不能相同或互相嵌套")

    media_paths: List[str] = []
    video_paths: List[str] = []
    for record in archived:
        if not isinstance(record, dict):
            raise ValueError("bookmarks.json 含非对象记录")
        for node in iter_tweet_nodes(record):
            media_values = node.get("media") or []
            if not isinstance(media_values, list):
                raise ValueError("bookmark 的 media 字段不是数组")
            for media in media_values:
                if not isinstance(media, dict):
                    raise ValueError("bookmark 含无效 media 记录")
                relative_path = str(media.get("localPath") or "")
                if not relative_path or Path(relative_path).name != relative_path:
                    raise ValueError("媒体路径不是单目录文件名：%s" % relative_path)
                target = (media_root / relative_path).resolve()
                if target.parent != media_root or not target.is_file() or target.stat().st_size <= 0:
                    raise ValueError("媒体文件缺失或为空：%s" % relative_path)
                media_paths.append(relative_path)
                if media.get("type") in {"video", "animated_gif"}:
                    video_paths.append(relative_path)

    if manifest.get("mediaCount") != len(media_paths):
        raise ValueError("manifest 的 mediaCount 与 bookmarks.json 不一致")
    if len(set(media_paths)) != len(media_paths):
        raise ValueError("归档含重复的媒体文件名")

    if video_paths:
        quality_path = metadata / "highest-resolution-report.json"
        if not quality_path.is_file():
            raise ValueError("含视频的归档缺少 highest-resolution-report.json")
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
        if not isinstance(quality, dict):
            raise ValueError("最高分辨率报告结构无效")
        if (
            quality.get("complete") is not True
            or quality.get("ytDlpExitCode") != 0
            or quality.get("videoReferences") != len(video_paths)
            or quality.get("replacedReferences") != len(video_paths)
            or quality.get("failedReferences") != 0
        ):
            raise ValueError("最高分辨率视频校验未完成或计数不一致")

    return archived, archived_ids


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    metadata = args.metadata.expanduser().resolve()
    try:
        _archived, archived_ids = validate_archive(metadata)
        LOG.info("本地归档完整性校验通过：%d 条", len(archived_ids))
        get_cookies, TwitterClient, load_config, tweet_to_dict, version = load_twitter_cli()
        cookies = get_cookies()
        config = load_config()
        client = TwitterClient(
            cookies["auth_token"],
            cookies["ct0"],
            config.get("rateLimit", {}),
            cookie_string=cookies.get("cookie_string"),
        )
        client._max_count = args.max_bookmarks
        LOG.info("使用 twitter-cli %s 读取当前 bookmarks……", version)
        live = client.fetch_bookmarks(args.max_bookmarks)
    except Exception as exc:
        LOG.error("安全预检或读取 bookmarks 失败：%s", exc)
        return 1

    live_ids = [str(tweet.id) for tweet in live]
    unarchived = [tweet_id for tweet_id in live_ids if tweet_id not in archived_ids]
    snapshot = {
        "schemaVersion": 1,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(live),
        "bookmarks": [tweet_to_dict(tweet) for tweet in live],
    }
    atomic_write_json(metadata / "pre-clear-bookmarks.json", snapshot)
    LOG.info("删除前快照已保存：%d 条", len(live))

    if unarchived and not args.allow_unarchived:
        LOG.error("发现 %d 条不在本地归档中的 bookmark；为避免丢失，尚未删除。", len(unarchived))
        LOG.error("ID：%s", ", ".join(unarchived[:20]))
        return 3
    if len(live) >= args.max_bookmarks:
        LOG.error("已达到安全上限，无法确认读取完整；请提高 --max-bookmarks 后重试。")
        return 3

    report: Dict[str, Any] = {
        "schemaVersion": 1,
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "requested": len(live_ids),
        "removed": [],
        "failed": [],
        "complete": False,
    }
    report_path = metadata / "clear-bookmarks-report.json"
    atomic_write_json(report_path, report)

    if not live_ids:
        report.update({"finishedAt": datetime.now(timezone.utc).isoformat(), "remaining": 0, "complete": True})
        atomic_write_json(report_path, report)
        LOG.info("当前 bookmarks 已经是 0。")
        return 0

    LOG.info("开始逐条取消 %d 个 bookmarks；twitter-cli 会自动控制写入间隔。", len(live_ids))
    for index, tweet_id in enumerate(live_ids, start=1):
        try:
            client.unbookmark_tweet(tweet_id)
            report["removed"].append(tweet_id)
            LOG.info("[%d/%d] 已取消 %s", index, len(live_ids), tweet_id)
        except Exception as exc:
            report["failed"].append({"id": tweet_id, "error": str(exc)})
            LOG.error("[%d/%d] 失败 %s：%s", index, len(live_ids), tweet_id, exc)
        if index % 5 == 0 or index == len(live_ids):
            atomic_write_json(report_path, report)

    try:
        remaining = client.fetch_bookmarks(args.max_bookmarks)
        remaining_ids = [str(tweet.id) for tweet in remaining]
    except Exception as exc:
        report["verificationError"] = str(exc)
        remaining_ids = []
        LOG.error("删除后验证失败：%s", exc)

    report["finishedAt"] = datetime.now(timezone.utc).isoformat()
    report["remaining"] = len(remaining_ids)
    report["remainingIds"] = remaining_ids
    report["complete"] = not report.get("verificationError") and len(remaining_ids) == 0
    atomic_write_json(report_path, report)

    if report["complete"]:
        LOG.info("验证完成：当前 bookmarks = 0。")
        return 0
    LOG.error("尚有 %d 个 bookmarks；可重新运行脚本继续清理。", len(remaining_ids))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
