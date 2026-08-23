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


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    metadata = args.metadata.expanduser().resolve()
    archive_path = metadata / "bookmarks.json"
    if not archive_path.is_file():
        LOG.error("找不到本地归档：%s", archive_path)
        return 1

    try:
        archived = json.loads(archive_path.read_text(encoding="utf-8"))
        if not isinstance(archived, list):
            raise ValueError("bookmarks.json 顶层不是数组")
        archived_ids = {str(item.get("id")) for item in archived if isinstance(item, dict) and item.get("id")}

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
        LOG.error("读取 bookmarks 或归档失败：%s", exc)
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
