---
name: manage-twitter-bookmarks
description: Archive, download, verify, and safely clear all Twitter/X bookmarks using twitter-cli. Use when Codex needs to back up bookmarks, download bookmark images and videos at the highest resolution X actually provides, keep a media-only target directory with separate metadata, resume an interrupted archive, validate media integrity, or remove/unbookmark every saved post after confirming it is archived.
---

# Manage Twitter Bookmarks

Resolve `SKILL_DIR` to the directory containing this file. Use the bundled scripts; do not reimplement pagination or destructive safety checks.

## Preconditions

Require these commands:

```bash
twitter --version
yt-dlp --version
ffprobe -version
```

Install missing Python tools from the package registry with `uv tool install twitter-cli` and `uv tool install yt-dlp`. Install FFmpeg from the platform's trusted package manager.

Execute all scripts directly through Codex. Authenticate through an existing X browser session or `TWITTER_AUTH_TOKEN` plus `TWITTER_CT0`. If macOS blocks browser-cookie access, grant Full Disk Access to Codex and restart it, or provide the two environment variables securely.

Choose two different sibling paths:

- `TARGET`: media only (`.mp4`, `.jpg`, `.png`, `.webp`); no JSON, Markdown, logs, or subdirectories.
- `METADATA`: `bookmarks.json`, per-post JSON/Markdown, manifests, and audit reports.

Default `METADATA` to `${TARGET}-metadata`.

## Archive and download

Run both stages in order:

```bash
"$SKILL_DIR/scripts/download_twitter_bookmarks.py" \
  --output "$TARGET" \
  --metadata-output "$METADATA" \
  --browser chrome

"$SKILL_DIR/scripts/upgrade_twitter_media_quality.py" \
  --output "$TARGET" \
  --metadata-output "$METADATA" \
  --browser chrome
```

The first script uses twitter-cli cursor pagination, saves original images, downloads the best direct MP4 variant, and resumes existing files. The second asks yt-dlp for every available HTTP/HLS format, chooses by resolution then bitrate, validates with FFprobe, and atomically replaces old videos. Treat “highest resolution” as the highest stream X currently exposes; never upscale lower-resolution sources.

Verify before reporting completion:

```bash
jq '{complete,bookmarkCount,mediaCount}' "$METADATA/manifest.json"
jq '{complete,videoReferences,replacedReferences,failedReferences}' \
  "$METADATA/highest-resolution-report.json"
find "$TARGET" -mindepth 1 -type d
find "$TARGET" -maxdepth 1 -type f \( -name '*.json' -o -name '*.md' \)
```

Require both reports to be complete, no missing/empty media, no target subdirectories, and no JSON/Markdown in `TARGET`. A `--metadata-only` run is deliberately marked incomplete when bookmarks contain media and is never sufficient for clearing online bookmarks.

## Clear all bookmarks

Only run this workflow when the user explicitly asks to remove, clear, or unbookmark the online X bookmarks. Never infer deletion from an archive/download request. Explain that online bookmark state is removed and not automatically recoverable, while the local archive remains.

Run directly through Codex:

```bash
"$SKILL_DIR/scripts/clear_twitter_bookmarks.py" --metadata "$METADATA"
```

The clear script must:

1. Require `manifest.json` to describe a complete cursor fetch and complete media download.
2. Verify every declared media file exists, is non-empty, and stays in the flat target directory.
3. For archives containing video, require a complete highest-resolution report with matching counts.
4. Fetch the live bookmark list and save `pre-clear-bookmarks.json` before the first mutation.
5. Compare every live ID with the local `bookmarks.json`.
6. Stop with exit code 3 if any live bookmark is unarchived.
7. Remove bookmarks one at a time with twitter-cli write delays.
8. Re-fetch and require `remaining: 0`.

If exit code 3 occurs, rerun the complete archive workflow, then retry clear. Do not pass `--allow-unarchived` unless the user explicitly authorizes deleting content absent from the local archive.

Report from `$METADATA/clear-bookmarks-report.json`. Require `complete: true`, `failed` length 0, and `remaining: 0`.

## Safety and handoff

- Preserve local media when clearing online bookmarks.
- Keep secrets out of commands, logs, Markdown, and reports.
- Do not trust nonzero files as valid video; use FFprobe.
- Resume after interruption instead of deleting the archive.
- State exact downloaded, failed, and remaining counts in the final response.
