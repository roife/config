---
name: music-lyrics-library
description: "Manage a local music library's lyrics: identify reliable lyric sources, compare title and artist metadata, clean and segment lyric text, add or repair timestamps, embed lyrics in M4A/MP3 files, and produce auditable verification reports. Use for requests to find, clean, synchronize, write, update, classify, or validate lyrics in a folder of audio files."
---

# Music Lyrics Library

Use this skill for a folder-level lyric workflow. Treat the audio files as the source of truth and keep every track in an audit record, including tracks that remain blank.

## User-facing workflow

Expose only these phases:

1. **Prepare** — scan the library, preserve a backup before destructive work, collect metadata, search sources, and produce review lists for reliable matches, pure music, and unresolved tracks.
2. **Process** — after confirmation, fetch or accept lyrics, clean non-lyric material, preserve meaningful parenthesized lines, segment by song structure, add timestamps when requested, and embed UTF-8 lyrics in the correct tag (`©lyr` for M4A, `USLT` for MP3).
3. **Review** — refresh candidate lists after the user edits files or metadata. Never overwrite a user-edited lyric without checking its current content.
4. **Verify** — reread every audio file, compare audit status, scan for residual timestamps/credits/advertising/placeholder text, and verify audio streams, artwork, and non-lyric metadata were not changed.

Resolve `SKILL_DIR` to the directory containing this file. Use the bundled launcher. It prefers `<LIBRARY>/music_lyrics.py` when present and otherwise runs the portable `scripts/core/lyrics_pipeline.py` under Python 3.12 with Mutagen. The launcher recognizes an Apple Music library at `<LIBRARY>/Music/Media.localized/Music`; pass `--media-root` for another layout.

The synchronized-lyrics helpers under `scripts/core/` preserve a historical, library-specific workflow and are audit/replay material. Do not run them as a generic pipeline. For timed lyrics, prefer a library's own `music_lyrics.py`; otherwise inspect and adapt the helpers' source maps, expected counts, backup path, and ML dependencies before use.

```bash
python3 "$SKILL_DIR/scripts/music_lyrics_skill.py" --library "$LIBRARY" inventory --hash
python3 "$SKILL_DIR/scripts/music_lyrics_skill.py" --library "$LIBRARY" fetch
python3 "$SKILL_DIR/scripts/music_lyrics_skill.py" --library "$LIBRARY" prepare
```

Review `$LIBRARY/.lyrics-work/review.md` and the prepared JSONL before asking for write confirmation. After confirmation, create and retain a separate APFS clone (or equivalent byte-preserving copy) of the media tree, then pass it explicitly:

```bash
python3 "$SKILL_DIR/scripts/music_lyrics_skill.py" --library "$LIBRARY" approve
python3 "$SKILL_DIR/scripts/music_lyrics_skill.py" \
  --library "$LIBRARY" --backup-root "$BACKUP" write
python3 "$SKILL_DIR/scripts/music_lyrics_skill.py" --library "$LIBRARY" verify --hash
python3 "$SKILL_DIR/scripts/music_lyrics_skill.py" \
  --library "$LIBRARY" --backup-root "$BACKUP" report
```

The bundled `write` command refuses to run without a separate backup whose audio path set and sizes match the baseline and whose files are not symlinks or hard links to the live library. Require `uv` and `ffmpeg`; the launcher provisions only the Python/Mutagen runtime.

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
