---
name: manage-twitter-bookmarks
description: Archive, resume, or verify Twitter/X bookmark archives using the bundled scripts, or clear online bookmarks after verifying their archive.
---

# Manage Twitter Bookmarks

Resolve `SKILL_DIR` to the directory containing this file. Use the bundled scripts; do not reimplement pagination or destructive safety checks.

## Choose the operation

- **Archive/refresh:** run download, then quality upgrade.
- **Resume:** reuse files and run the unfinished stage; quality recovery alone needs no new bookmark fetch.
- **Verify:** use local validation below. Fetch/download only for requested repair or refresh.
- **Metadata export:** add `--metadata-only` to download. `bookmarkFetchComplete: true` finishes this request even if skipped media cause exit code 2 and `complete: false`. This does not qualify the archive for clearing.

## Setup when needed

Download/clear need `twitter-cli`; video upgrade needs `yt-dlp` and FFmpeg/FFprobe; local validation needs Python only. Check dependencies once per unchanged environment. Install missing tools only for the selected operation: `uv tool install twitter-cli`, `uv tool install yt-dlp`, or FFmpeg through the platform package manager.

Use the authenticated browser for `X_BROWSER` and `TWITTER_BROWSER`. Download/clear also accept securely supplied `TWITTER_AUTH_TOKEN` and `TWITTER_CT0`; video upgrade currently requires browser cookies. For blocked macOS cookie access, Full Disk Access and restarting Codex are optional user-controlled remedies. Keep secrets out of commands, logs, and reports.

Choose sibling directories, defaulting `METADATA` to `${TARGET}-metadata`:

- `TARGET`: flat media only (`.mp4`, `.jpg`, `.png`, `.webp`).
- `METADATA`: bookmark JSON/Markdown, manifests, and reports.

## Archive and download

```bash
"$SKILL_DIR/scripts/download_twitter_bookmarks.py" \
  --output "$TARGET" \
  --metadata-output "$METADATA" \
  --browser "$X_BROWSER"

"$SKILL_DIR/scripts/upgrade_twitter_media_quality.py" \
  --output "$TARGET" \
  --metadata-output "$METADATA" \
  --browser "$X_BROWSER"
```

Download preserves original images; upgrade selects videos by resolution then bitrate and replaces them atomically. Highest resolution means what X exposes; never upscale. Upgrade probes candidates and installed files with FFprobe; repeat probing only if files changed or those results no longer apply.

## Validate a full archive

```bash
"$SKILL_DIR/scripts/clear_twitter_bookmarks.py" \
  --metadata "$METADATA" --validate-only
```

This locally checks completeness, media paths/counts, nonempty files, flat layout, and matching video-quality results. It neither authenticates nor contacts X. Run before reporting a full archive complete; clear performs these checks itself.

## Clear all bookmarks

Require an explicit request to clear online bookmarks; it also authorizes recovery within that scope without repeated confirmation. Explain that online bookmark state is removed and not automatically recoverable. Preserve the local archive.

```bash
"$SKILL_DIR/scripts/clear_twitter_bookmarks.py" --metadata "$METADATA"
```

The script validates the archive, snapshots live bookmarks, checks ID coverage, paces removals, and verifies the remaining count.

For exit code 3, follow the diagnostic: archive missing IDs, or increase the fetch's `--max-bookmarks` cap and retry. Never bypass an incomplete fetch. Retry while making progress; report persistent blockers. Use `--allow-unarchived` only with explicit authorization to delete unarchived content.

Report from `$METADATA/clear-bookmarks-report.json`. Require `complete: true`, `failed` length 0, and `remaining: 0`.

## Report

Report applicable downloaded, reused, upgraded, failed, and removed counts from the manifest and reports. Online remaining counts require a successful live fetch; otherwise say unverified. Resume after interruption instead of deleting the archive.
