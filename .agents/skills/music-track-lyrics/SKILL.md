---
name: music-track-lyrics
description: "Inspect, find, clean, synchronize, or embed lyrics for one local M4A or MP3 file. Use for a specific audio file, not a folder or music-library batch."
---

# Music Track Lyrics

Work on the single M4A or MP3 the user identified. Keep paths, endpoints, candidate choices, thresholds and backup destinations explicit in command arguments. Avoid scanning sibling files or invoking a library-wide pipeline.

Resolve `SKILL_DIR` to this skill directory. All implementation lives in `scripts/music_track_lyrics.py`. Each capability is an independent top-level function and an independent CLI subcommand. Run it with `uv run`; every subcommand requires `--audio` and emits one JSON object unless it is the final report writer.

## Choose the stopping point

- For inspection or lookup, return the requested tag information, recording match or unresolved candidates. For a proposed cleanup or alignment, return the reviewed proposal and identify any estimated timing.
- For an authorized embed, take a supported proposal through approval, backup and verified write. Resolve routine choices using track metadata and the source evidence. If two versions remain plausible, present the distinguishing details before changing the file.
- In the result, identify the track and say whether its tag was changed. After a write, give the verified result and the retained backup path. If verification fails, report the observed file and rollback status.

## Entrypoints

- `inspect_track()` / `inspect` — capture metadata, current lyrics, logical tags, artwork, streams, and hashes.
- `search_source()` / `search` — search one explicitly named provider endpoint.
- `fetch_source()` / `fetch` — fetch one explicitly selected search candidate.
- `match_source()` / `match` — compare one fetched source with the track; require an explicit duration tolerance and optional alias map.
- `clean_track_lyrics()` / `clean` — remove logged non-lyric material while preserving lyric wording.
- `segment_track_lyrics()` / `segment` — add logged paragraph boundaries from explicit line choices or timestamp gaps.
- `align_track_lyrics()` / `align` — align plain lyrics to an existing synchronized source; accept explicit per-line overrides and never transcribe audio.
- `classify_track()` / `classify` — classify the track as lyrical, instrumental, or unresolved using explicit evidence.
- `approve_change()` / `approve` — bind an accept/reject decision to one immutable proposal and the current file state.
- `backup_track()` / `backup` — create and verify one independent byte-preserving backup at an explicit destination.
- `write_track_lyrics()` / `write` — write one approved proposal after proving the backup matches; roll back on failed invariant checks.
- `verify_track()` / `verify` — compare the result with one explicit baseline and proposal.
- `report_track()` / `report` — combine records for this track into one JSON audit and one Markdown report.

Consult [references/interfaces.md](references/interfaces.md) when input/output contracts are unclear; use subcommand `--help` for flags. Read [references/cleaning.md](references/cleaning.md) when applying or reviewing its text and classification rules.

## Invariants

- Treat the audio file as the source of truth. `approve` captures its current hashes; `write` checks them and captures fresh before/after snapshots. A separate full inspection is unnecessary unless the task needs a baseline artifact.
- A source is writable only when title, artist, version, and duration support the same recording. Keep live, remix, cover, TV-size, instrumental, and accompaniment variants distinct.
- Preserve lyric wording. Treat interpolated timestamps as draft estimates requiring review. Overrides supplement a required synchronized source; they do not replace it.
- Write UTF-8 lyrics to `©lyr` for M4A/MP4 and `USLT` for MP3. Do not re-encode audio or change artwork or unrelated tags.
- Never write without an explicit accepted approval record and an independent, byte-identical backup. Preserve the backup after success.
- An approval record may document authorization already provided by the user; do not request the same authorization again. Review candidates within the authorized scope. If a material unresolved choice remains, prepare the concrete proposal before asking about that choice.
- Plain lyrics are the default. Use synchronized LRC only when requested.
- Leave already-empty unresolved or confirmed-instrumental tracks empty. Preserve existing lyrics unless the requested change includes replacing or removing them. Remove verified placeholder-only text when cleanup is authorized.
- A successful `write` result includes full post-write verification and satisfies routine verification. Use `verify` for an independent, later or explicitly requested check. Use `report` when an audit artifact is requested.
