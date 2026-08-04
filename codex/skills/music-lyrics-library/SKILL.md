---
name: music-lyrics-library
description: Manage a local music library's lyrics: identify reliable lyric sources, compare title and artist metadata, clean and segment lyric text, add or repair timestamps, embed lyrics in M4A/MP3 files, and produce auditable verification reports. Use for requests to find, clean, synchronize, write, update, classify, or validate lyrics in a folder of audio files.
---

# Music Lyrics Library

Use this skill for a folder-level lyric workflow. Treat the audio files as the source of truth and keep every track in an audit record, including tracks that remain blank.

## User-facing workflow

Expose only these phases:

1. **Prepare** — scan the library, preserve a backup before destructive work, collect metadata, search sources, and produce review lists for reliable matches, pure music, and unresolved tracks.
2. **Process** — after confirmation, fetch or accept lyrics, clean non-lyric material, preserve meaningful parenthesized lines, segment by song structure, add timestamps when requested, and embed UTF-8 lyrics in the correct tag (`©lyr` for M4A, `USLT` for MP3).
3. **Review** — refresh candidate lists after the user edits files or metadata. Never overwrite a user-edited lyric without checking its current content.
4. **Verify** — reread every audio file, compare audit status, scan for residual timestamps/credits/advertising/placeholder text, and verify audio streams, artwork, and non-lyric metadata were not changed.

Use the bundled launcher when the library already contains `music_lyrics.py`; otherwise locate the equivalent pipeline scripts in the target folder before acting. Prefer the existing local pipeline over rewriting one-off code.

The session's core implementations are bundled under `scripts/core/` (`lyrics_pipeline.py`, `add_timed_lyrics.py`, source/candidate helpers, and alignment support). They preserve the original workflow for audit/replay; use the launcher or a target library's consolidated entry point for normal operations. These historical modules may contain library-specific absolute paths and should be adapted before using them on a different machine.

```bash
python3 music_lyrics.py prepare
python3 music_lyrics.py review
python3 music_lyrics.py write --timed
python3 music_lyrics.py timing verify
python3 music_lyrics.py verify
```

Do not write a candidate when title, artist, version, and duration do not support the same recording. Small duration differences are acceptable; remix, live, cover, TV-size, instrumental, and accompaniment variants must remain distinct. Preserve artist aliases and collaboration differences in the audit log rather than silently normalizing them away. Do not use machine transcription to invent missing lyrics.

## Source and matching policy

Prefer existing ISRC, MusicBrainz, and AcoustID identifiers, then exact title/artist/album searches. Use trusted lyric sources such as LRCLIB, NetEase, Spotify-linked sources, Bandcamp, and official artist/album pages as available. Request sources conservatively with low parallelism and a delay when a service is rate-limited. `Любэ` and `Lube` may be treated as an alias only after the recording context agrees; do not re-request excluded artists when the user says so.

For every selected source record: source URL/provider, local metadata, normalized match, title/artist/version differences, manual confirmation, cleaned-line categories, removed timestamp count, new paragraph boundaries, and post-write verification. See [cleanup-rules.md](references/cleanup-rules.md) for the cleaning contract.

## Safety and deliverables

- Create an APFS clone or equivalent backup before bulk writes and retain it.
- Keep unresolved and confirmed-instrumental tracks blank; remove placeholder-only lyrics.
- Write plain lyric text unless timestamps were explicitly requested.
- Never modify audio encoding, streams, cover art, or unrelated metadata.
- Produce both Markdown and JSONL audit reports with one record per audio file.
- When reporting results, summarize counts and link to the audit files; list exceptions that need user judgment.
