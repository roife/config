---
name: manage-twitter-bookmarks
description: Archive, resume, or verify Twitter/X bookmark archives using the bundled scripts, or clear online bookmarks after verifying their archive.
---

# Manage Twitter Bookmarks

Resolve `SKILL_DIR` to the directory containing this file. Use the bundled scripts; do not reimplement pagination or destructive safety checks.

## Choose the operation

- **Archive or refresh** the requested collection through download, video quality upgrade where applicable, and local validation.
- **Resume** from the existing media directory, manifest and quality report. Run the first incomplete stage and the remaining checks for the requested outcome. A quality-only repair can reuse the bookmark snapshot.
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

When clear exits with code 3, follow the current diagnostic. For missing IDs, refresh and validate the archive before retrying. For a capped live snapshot, raise `--max-bookmarks` on the clear command so its own preflight can establish coverage. Use `--allow-unarchived` only with explicit authorization to delete unarchived content. After a partial clear, use the current run’s report and retry through the same preflight while progress is possible. An earlier report can survive a failed preflight and cannot establish the outcome of this run.

Report from `$METADATA/clear-bookmarks-report.json`. Require `complete: true`, `failed` length 0, and `remaining: 0`.

## Report

Identify the operation and the media and metadata paths so the user can reopen or resume the archive. Report applicable downloaded, reused, upgraded, failed, and removed counts from the manifest and reports. Online remaining counts require a successful live fetch; otherwise say unverified. Resume after interruption instead of deleting the archive.
