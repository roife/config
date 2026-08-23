#!/usr/bin/env python3
"""Archive every Twitter/X bookmark with twitter-cli.

The script uses twitter-cli's authenticated client so that pagination continues
until X stops returning a cursor.  It writes a JSON snapshot, one Markdown/JSON
pair per bookmark, and downloads attached images/videos. All generated files
share one flat output directory. Existing media files are reused, so an
interrupted run can simply be started again.

Authentication is the same as twitter-cli itself:

  1. Log in to https://x.com in a supported local browser; or
  2. export TWITTER_AUTH_TOKEN='...'
     export TWITTER_CT0='...'

Run:

  ./download_twitter_bookmarks.py --output ./twitter-bookmarks
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import mimetypes
import os
import re
import shlex
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


LOG = logging.getLogger("bookmark-archive")
REEXEC_GUARD = "TWITTER_BOOKMARK_ARCHIVER_REEXECUTED"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133 Safari/537.36"
)


def _twitter_cli_python() -> Optional[str]:
    """Return the Python interpreter from the installed `twitter` launcher."""
    launcher = shutil.which("twitter")
    if not launcher:
        return None

    try:
        first_line = Path(launcher).read_text(encoding="utf-8").splitlines()[0]
    except (OSError, UnicodeError, IndexError):
        return None
    if not first_line.startswith("#!"):
        return None

    try:
        command = shlex.split(first_line[2:].strip())
    except ValueError:
        return None
    if not command:
        return None

    # uv-installed tools normally use an absolute interpreter in the shebang.
    # Handle `/usr/bin/env python3` as a convenience for other installations.
    if Path(command[0]).name == "env" and len(command) >= 2:
        return shutil.which(command[1])
    return command[0] if Path(command[0]).exists() else None


def _load_twitter_cli() -> Tuple[Any, Any, Any, str]:
    """Import twitter-cli, re-executing with its isolated Python if needed."""
    try:
        import twitter_cli
        from twitter_cli.auth import get_cookies
        from twitter_cli.client import TwitterClient
        from twitter_cli.config import load_config

        return get_cookies, TwitterClient, load_config, getattr(twitter_cli, "__version__", "unknown")
    except ImportError as exc:
        interpreter = _twitter_cli_python()
        already_reexecuted = os.environ.get(REEXEC_GUARD) == "1"
        if interpreter and not already_reexecuted and Path(interpreter).resolve() != Path(sys.executable).resolve():
            env = os.environ.copy()
            env[REEXEC_GUARD] = "1"
            os.execve(interpreter, [interpreter, str(Path(__file__).resolve()), *sys.argv[1:]], env)
        raise RuntimeError(
            "找不到 twitter-cli。请先安装：uv tool install twitter-cli\n"
            "如果已经安装，请确认 `twitter --version` 可以运行。"
        ) from exc


@dataclass(frozen=True)
class MediaJob:
    url: str
    target: Path
    bookmark_id: str


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="用 twitter-cli 完整归档 Twitter/X bookmarks（JSON、Markdown 和媒体）。"
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
        help="JSON/Markdown 目录（默认：在 target 旁边加 -metadata）",
    )
    parser.add_argument(
        "--max-bookmarks",
        type=int,
        default=100_000,
        help="防止异常无限翻页的安全上限（默认：100000）",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="只保存 JSON/Markdown，不下载图片和视频",
    )
    parser.add_argument(
        "--flatten-existing",
        action="store_true",
        help="仅把旧版 items/ 分目录归档迁移成单目录布局，不访问 Twitter/X",
    )
    parser.add_argument(
        "--refresh-media",
        action="store_true",
        help="重新下载已经存在的媒体文件",
    )
    parser.add_argument("--jobs", type=int, default=4, help="并发下载数（默认：4）")
    parser.add_argument("--retries", type=int, default=3, help="媒体下载重试次数（默认：3）")
    parser.add_argument("--timeout", type=float, default=60.0, help="单次下载超时秒数（默认：60）")
    parser.add_argument(
        "--browser",
        choices=("arc", "chrome", "edge", "firefox", "brave"),
        help="指定 twitter-cli 从哪个浏览器读取 X 登录 Cookie",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="显示调试日志")
    args = parser.parse_args(argv)
    if args.max_bookmarks <= 0:
        parser.error("--max-bookmarks 必须大于 0")
    if args.jobs <= 0:
        parser.error("--jobs 必须大于 0")
    if args.retries < 0:
        parser.error("--retries 不能小于 0")
    if args.timeout <= 0:
        parser.error("--timeout 必须大于 0")
    return args


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp-%d" % (path.name, os.getpid()))
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def permalink(tweet: Any) -> str:
    screen_name = getattr(getattr(tweet, "author", None), "screen_name", "")
    tweet_id = str(getattr(tweet, "id", ""))
    if screen_name:
        return "https://x.com/%s/status/%s" % (screen_name, tweet_id)
    return "https://x.com/i/status/%s" % tweet_id


def tweet_to_full_dict(tweet: Any) -> Dict[str, Any]:
    """Serialize a Tweet while retaining nested quoted-tweet content and media."""
    from twitter_cli.serialization import tweet_to_dict

    data = tweet_to_dict(tweet)
    data["permalink"] = permalink(tweet)
    quoted = getattr(tweet, "quoted_tweet", None)
    if quoted is not None:
        data["quotedTweet"] = tweet_to_full_dict(quoted)
    return data


def media_extension(url: str, media_type: str) -> str:
    path_suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
    if re.fullmatch(r"\.[a-z0-9]{1,5}", path_suffix):
        return path_suffix
    content_type = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("format", [""])[0]
    if content_type:
        guessed = mimetypes.guess_extension("image/%s" % content_type.lower())
        if guessed:
            return guessed
    return ".jpg" if media_type == "photo" else ".mp4"


def best_media_url(url: str, media_type: str) -> str:
    """Ask pbs.twimg.com for the original image; video URL is already best bitrate."""
    if media_type != "photo" or "pbs.twimg.com" not in urllib.parse.urlsplit(url).netloc:
        return url
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
    query["name"] = ["orig"]
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query, doseq=True), parts.fragment)
    )


def flat_media_filename(
    bookmark_id: str,
    trail: Tuple[str, ...],
    index: int,
    url: str,
    media_type: str,
) -> str:
    suffix = "-".join((*trail, "%02d" % index))
    return "tweet-%s-%s%s" % (bookmark_id, suffix, media_extension(url, media_type))


def add_local_media_paths(
    archive_root: Path,
    bookmark_id: str,
    tweet: Any,
    data: Dict[str, Any],
    trail: Tuple[str, ...] = (),
) -> List[MediaJob]:
    jobs: List[MediaJob] = []
    media_values = list(getattr(tweet, "media", []) or [])
    data_values = data.get("media") if isinstance(data.get("media"), list) else []
    for index, (media, media_data) in enumerate(zip(media_values, data_values), start=1):
        media_type = str(getattr(media, "type", ""))
        source_url = best_media_url(str(getattr(media, "url", "")), media_type)
        filename = flat_media_filename(bookmark_id, trail, index, source_url, media_type)
        target = archive_root / filename
        media_data["downloadUrl"] = source_url
        media_data["localPath"] = filename
        jobs.append(MediaJob(source_url, target, bookmark_id))

    quoted_tweet = getattr(tweet, "quoted_tweet", None)
    quoted_data = data.get("quotedTweet")
    if quoted_tweet is not None and isinstance(quoted_data, dict):
        jobs.extend(
            add_local_media_paths(
                archive_root,
                bookmark_id,
                quoted_tweet,
                quoted_data,
                (*trail, "quoted"),
            )
        )
    return jobs


def markdown_for_tweet(data: Dict[str, Any], archive_root: Path, item_dir: Path, heading: int = 1) -> str:
    author = data.get("author") or {}
    title = "%s (@%s)" % (author.get("name", ""), author.get("screenName", ""))
    lines = ["%s %s" % ("#" * heading, title.strip()), ""]
    if data.get("createdAtISO"):
        lines.extend(["- 时间：%s" % data["createdAtISO"]])
    lines.extend(["- 原文：%s" % data.get("permalink", ""), "", str(data.get("text", "")).strip(), ""])

    article_title = data.get("articleTitle")
    article_text = data.get("articleText")
    if article_title or article_text:
        lines.extend(["%s Twitter Article" % ("#" * min(heading + 1, 6)), ""])
        if article_title:
            lines.extend(["**%s**" % article_title, ""])
        if article_text:
            lines.extend([str(article_text).strip(), ""])

    urls = [url for url in data.get("urls", []) if url]
    if urls:
        lines.extend(["%s 链接" % ("#" * min(heading + 1, 6)), ""])
        lines.extend(["- %s" % url for url in urls])
        lines.append("")

    media = data.get("media") or []
    if media:
        lines.extend(["%s 媒体" % ("#" * min(heading + 1, 6)), ""])
        for value in media:
            local_path = archive_root / str(value.get("localPath", ""))
            relative = os.path.relpath(local_path, item_dir)
            if value.get("type") == "photo":
                lines.append("![图片](%s)" % Path(relative).as_posix())
            else:
                lines.append("[%s](%s)" % (value.get("type", "视频"), Path(relative).as_posix()))
            lines.append("")

    quoted = data.get("quotedTweet")
    if isinstance(quoted, dict):
        lines.extend(["%s 引用推文" % ("#" * min(heading + 1, 6)), ""])
        lines.extend(markdown_for_tweet(quoted, archive_root, item_dir, min(heading + 2, 6)).splitlines())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def download_one(job: MediaJob, refresh: bool, timeout: float, retries: int) -> Tuple[MediaJob, str]:
    target = job.target
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size > 0 and not refresh:
        return job, "skipped"

    partial = target.with_name(target.name + ".part")
    for attempt in range(retries + 1):
        try:
            existing = partial.stat().st_size if partial.exists() else 0
            headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "*/*"}
            if existing:
                headers["Range"] = "bytes=%d-" % existing
            request = urllib.request.Request(job.url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                append = existing > 0 and getattr(response, "status", None) == 206
                with partial.open("ab" if append else "wb") as output:
                    shutil.copyfileobj(response, output, length=1024 * 1024)
            if not partial.exists() or partial.stat().st_size == 0:
                raise OSError("服务器返回了空文件")
            os.replace(partial, target)
            return job, "downloaded"
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            if attempt >= retries:
                return job, "error: %s" % exc
            time.sleep(min(2**attempt, 8))
    return job, "error: unknown"


def render_index(records: Iterable[Dict[str, Any]]) -> str:
    lines = ["# Twitter/X Bookmarks", ""]
    for data in records:
        author = data.get("author") or {}
        bookmark_id = str(data.get("id", ""))
        link = "tweet-%s.md" % bookmark_id
        text = re.sub(r"\s+", " ", str(data.get("text", ""))).strip()
        if len(text) > 120:
            text = text[:117] + "..."
        lines.append("- [%s · @%s](%s) — %s" % (data.get("createdAtISO", ""), author.get("screenName", ""), link, text))
    lines.append("")
    return "\n".join(lines)


def _safe_archive_path(archive_root: Path, relative_path: str) -> Path:
    resolved_root = archive_root.resolve()
    candidate = (resolved_root / relative_path).resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise RuntimeError("归档中包含越界路径：%s" % relative_path)
    return candidate


def _flatten_record_media(
    archive_root: Path,
    bookmark_id: str,
    data: Dict[str, Any],
    trail: Tuple[str, ...] = (),
) -> int:
    moved = 0
    media_values = data.get("media") if isinstance(data.get("media"), list) else []
    for index, media_data in enumerate(media_values, start=1):
        if not isinstance(media_data, dict):
            continue
        media_type = str(media_data.get("type", ""))
        source_url = str(media_data.get("downloadUrl") or media_data.get("url") or "")
        filename = flat_media_filename(bookmark_id, trail, index, source_url, media_type)
        target = archive_root / filename
        old_relative = str(media_data.get("localPath") or "")
        old_path = _safe_archive_path(archive_root, old_relative) if old_relative else target

        if old_path != target and old_path.exists():
            if target.exists():
                if old_path.stat().st_size != target.stat().st_size:
                    raise RuntimeError("目标文件冲突且大小不同：%s" % target)
                old_path.unlink()
            else:
                os.replace(old_path, target)
            moved += 1
        elif not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError("找不到媒体文件：%s" % old_relative)
        media_data["localPath"] = filename

    quoted = data.get("quotedTweet")
    if isinstance(quoted, dict):
        moved += _flatten_record_media(archive_root, bookmark_id, quoted, (*trail, "quoted"))
    return moved


def flatten_existing_archive(archive_root: Path, metadata_root: Path) -> int:
    """Migrate the old items/<id>/... layout without another network fetch."""
    archive_root = archive_root.expanduser().resolve()
    metadata_root = metadata_root.expanduser().resolve()
    metadata_root.mkdir(parents=True, exist_ok=True)
    bookmarks_path = metadata_root / "bookmarks.json"
    legacy_bookmarks_path = archive_root / "bookmarks.json"
    if not bookmarks_path.is_file() and legacy_bookmarks_path.is_file():
        bookmarks_path = legacy_bookmarks_path
    if not bookmarks_path.is_file():
        LOG.error("找不到现有归档：%s", bookmarks_path)
        return 1
    try:
        records = json.loads(bookmarks_path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("bookmarks.json 顶层不是数组")

        moved = 0
        for data in records:
            if not isinstance(data, dict):
                continue
            bookmark_id = str(data.get("id", ""))
            if not bookmark_id or not bookmark_id.isdigit():
                raise ValueError("无效的 bookmark ID：%s" % bookmark_id)
            moved += _flatten_record_media(archive_root, bookmark_id, data)
            atomic_write_text(metadata_root / ("tweet-%s.json" % bookmark_id), json_text(data))
            atomic_write_text(
                metadata_root / ("tweet-%s.md" % bookmark_id),
                markdown_for_tweet(data, archive_root, metadata_root),
            )

        atomic_write_text(metadata_root / "bookmarks.json", json_text(records))
        atomic_write_text(metadata_root / "index.md", render_index(records))

        manifest_path = metadata_root / "manifest.json"
        legacy_manifest_path = archive_root / "manifest.json"
        if not manifest_path.is_file() and legacy_manifest_path.is_file():
            manifest_path = legacy_manifest_path
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(manifest, dict):
                manifest["layout"] = "flat"
                atomic_write_text(metadata_root / "manifest.json", json_text(manifest))

        # Remove only files generated by the legacy archive layout.  Do this
        # after the separated metadata copies have been written successfully.
        for legacy_file in (
            archive_root / "bookmarks.json",
            archive_root / "manifest.json",
            archive_root / "index.md",
        ):
            if legacy_file.is_file():
                legacy_file.unlink()

        legacy_root = archive_root / "items"
        if legacy_root.is_dir():
            remaining = [path for path in legacy_root.rglob("*") if path.is_file()]
            unexpected = [path for path in remaining if path.name not in {"tweet.json", "content.md"}]
            if unexpected:
                raise RuntimeError("旧目录仍含未迁移文件：%s" % unexpected[0])
            for path in remaining:
                path.unlink()
            for directory in sorted(
                (path for path in legacy_root.rglob("*") if path.is_dir()),
                key=lambda path: len(path.parts),
                reverse=True,
            ):
                directory.rmdir()
            legacy_root.rmdir()
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        LOG.error("扁平化迁移失败：%s", exc)
        return 1

    LOG.info("扁平化完成：%d 条 bookmark，移动 %d 个媒体文件", len(records), moved)
    LOG.info("媒体 target：%s", archive_root)
    LOG.info("JSON/Markdown：%s", metadata_root)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    archive_root = args.output.expanduser().resolve()
    metadata_root = (
        args.metadata_output.expanduser().resolve()
        if args.metadata_output is not None
        else archive_root.with_name(archive_root.name + "-metadata")
    )
    if (
        archive_root == metadata_root
        or archive_root in metadata_root.parents
        or metadata_root in archive_root.parents
    ):
        LOG.error("媒体 target 与 metadata 目录必须彼此分离，且不能互相嵌套。")
        return 1
    if args.flatten_existing:
        return flatten_existing_archive(archive_root, metadata_root)
    if args.browser:
        os.environ["TWITTER_BROWSER"] = args.browser

    try:
        get_cookies, TwitterClient, load_config, twitter_cli_version = _load_twitter_cli()
        LOG.info("使用 twitter-cli %s 读取认证信息", twitter_cli_version)
        cookies = get_cookies()
        config = load_config()
        rate_limit = config.get("rateLimit", {})
        client = TwitterClient(
            cookies["auth_token"],
            cookies["ct0"],
            rate_limit,
            cookie_string=cookies.get("cookie_string"),
        )

        # twitter-cli 0.8.x deliberately caps normal CLI commands at 500. This
        # archive command raises the instance cap but keeps its pagination,
        # deduplication, delays, retry handling, and cursor termination intact.
        client._max_count = args.max_bookmarks
        LOG.info("开始遍历 bookmarks；到达末页后会自动停止……")
        tweets = client.fetch_bookmarks(args.max_bookmarks)
    except Exception as exc:
        LOG.error("读取 bookmarks 失败：%s", exc)
        if "No Twitter cookies" in str(exc):
            LOG.error(
                "请先在 Arc/Chrome/Edge/Firefox/Brave 登录 x.com，或设置 "
                "TWITTER_AUTH_TOKEN 和 TWITTER_CT0。"
            )
        return 1

    archive_root.mkdir(parents=True, exist_ok=True)
    metadata_root.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, Any]] = []
    jobs: List[MediaJob] = []
    for tweet in tweets:
        bookmark_id = str(tweet.id)
        data = tweet_to_full_dict(tweet)
        jobs.extend(add_local_media_paths(archive_root, bookmark_id, tweet, data))
        records.append(data)

        atomic_write_text(metadata_root / ("tweet-%s.json" % bookmark_id), json_text(data))
        atomic_write_text(
            metadata_root / ("tweet-%s.md" % bookmark_id),
            markdown_for_tweet(data, archive_root, metadata_root),
        )

    fetched_at = datetime.now(timezone.utc).isoformat()
    reached_limit = len(records) >= args.max_bookmarks
    manifest = {
        "schemaVersion": 1,
        "fetchedAt": fetched_at,
        "twitterCliVersion": twitter_cli_version,
        "bookmarkCount": len(records),
        "mediaCount": len(jobs),
        "layout": "flat",
        "complete": not reached_limit,
        "warning": (
            "已达到 --max-bookmarks 安全上限；请提高上限后重试。" if reached_limit else None
        ),
    }
    atomic_write_text(metadata_root / "bookmarks.json", json_text(records))
    atomic_write_text(metadata_root / "index.md", render_index(records))
    atomic_write_text(metadata_root / "manifest.json", json_text(manifest))
    LOG.info("已保存 %d 条 bookmark 的 JSON/Markdown", len(records))

    failures: List[Tuple[MediaJob, str]] = []
    if not args.metadata_only and jobs:
        counts = {"downloaded": 0, "skipped": 0}
        LOG.info("准备处理 %d 个媒体文件（%d 路并发）", len(jobs), args.jobs)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = [
                executor.submit(download_one, job, args.refresh_media, args.timeout, args.retries)
                for job in jobs
            ]
            for future in concurrent.futures.as_completed(futures):
                job, status = future.result()
                if status.startswith("error:"):
                    failures.append((job, status))
                    LOG.warning("媒体下载失败（bookmark %s）：%s — %s", job.bookmark_id, job.url, status)
                else:
                    counts[status] += 1
        manifest["mediaDownloaded"] = counts["downloaded"]
        manifest["mediaSkipped"] = counts["skipped"]
        manifest["mediaFailed"] = len(failures)
        atomic_write_text(metadata_root / "manifest.json", json_text(manifest))
        LOG.info("媒体完成：新下载 %d，已存在 %d，失败 %d", counts["downloaded"], counts["skipped"], len(failures))
    elif args.metadata_only:
        LOG.info("--metadata-only：已跳过媒体下载")

    LOG.info("媒体 target：%s", archive_root)
    LOG.info("JSON/Markdown：%s", metadata_root)
    if reached_limit:
        LOG.warning("已碰到安全上限，不能确认归档完整；请提高 --max-bookmarks 后重跑。")
    return 2 if failures or reached_limit else 0


if __name__ == "__main__":
    raise SystemExit(main())
