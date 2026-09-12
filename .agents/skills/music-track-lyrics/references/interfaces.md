# Single-track interface contract

Every public function and CLI subcommand accepts exactly one audio file. Subcommands require `--audio AUDIO_FILE`; they reject unsupported or missing files and never enumerate sibling files or directories. Inputs and outputs are UTF-8. JSON-producing commands write to stdout unless `--output OUTPUT_JSON` is supplied.

Run commands as `uv run "$SKILL_DIR/scripts/music_track_lyrics.py" SUBCOMMAND ...`. The same operations are importable as top-level Python functions. Use task-specific variables such as `AUDIO_FILE`, `TASK_DIR`, and `BACKUP_FILE`; do not rely on a current music-library directory.

## Records and composition

Every record contains the absolute `audio_path` and a versioned `schema`. Downstream commands, including JSON lyric inputs, check the track identity before extracting content. Plain-text lyric inputs carry no track identity and are treated as deliberately supplied text for `--audio`.

1. `inspect --audio AUDIO_FILE --output BASELINE_JSON`
   - Produces the pre-change baseline, including whole-file, lyric, tag, artwork, audio-payload, and stream evidence.
   - Use when the request needs this snapshot; `write` captures its own baseline and verifies the result.

2. `search --audio AUDIO_FILE --provider PROVIDER --endpoint SEARCH_ENDPOINT --output SEARCH_JSON`
   - Supported provider response shapes are `lrclib` and `netease`.
   - The endpoint is mandatory; the script contains no provider URL or source selection.
   - Use `--query` only when the track metadata is insufficient.

3. `fetch --audio AUDIO_FILE --search-record SEARCH_JSON --candidate-index INDEX --endpoint FETCH_ENDPOINT --output SOURCE_JSON`
   - Fetches only the explicitly indexed candidate.
   - For endpoints with an ID in the path, use an endpoint containing `{id}` or a base endpoint to which the ID can be appended.

4. `match --audio AUDIO_FILE --source-record SOURCE_JSON --duration-tolerance SECONDS --output MATCH_JSON`
   - An optional `--aliases ALIASES_JSON` accepts one explicit JSON object mapping artist spellings to canonical forms.
   - No artist, title, album, path, source ID, or version override is built in.

5. `clean --audio AUDIO_FILE --lyrics INPUT --output CLEAN_JSON`
   - `INPUT` can be plain text, a compatible JSON record, or `-` for stdin.
   - The output is a proposal with `lyrics`, hashes, transformations, and residual flags.
   - Title-matching lines are preserved by default. Repeat `--heading-line LINE_NUMBER` for one-based source lines confirmed to be headings; only matching title or title-plus-artist text on those lines is removed.

6. `segment --audio AUDIO_FILE --lyrics INPUT --gap-seconds SECONDS --output SEGMENT_JSON`
   - Repeat `--break-before LINE_NUMBER` for reviewed, one-based lyric-line boundaries.
   - Timestamp gaps may add boundaries. Plain text is otherwise not segmented speculatively.

7. `align --audio AUDIO_FILE --lyrics PLAIN_INPUT --timed-source LRC_INPUT --minimum-similarity SCORE --split-window-seconds SECONDS --output TIMED_JSON`
   - `--overrides OVERRIDES_JSON` accepts a JSON object mapping zero-based lyric-line indexes to seconds.
   - Overrides supplement the required synchronized source. Every interpolated timestamp remains a draft estimate and causes `review` status unless replaced by an explicit override.
   - Inspect a `review` result before approval. The agent may perform this review within the authorized task; request user input only for a material unresolved choice.

8. `classify --audio AUDIO_FILE --output CLASSIFICATION_JSON`
   - Use `--lyrics INPUT` to classify proposed text rather than the embedded tag.
   - Use `--source-record SOURCE_JSON` or repeat `--instrumental-evidence TEXT` for affirmative instrumental evidence.
   - An empty provider response alone remains unresolved.

9. `approve --audio AUDIO_FILE --proposal PROPOSAL_JSON --decision accept|reject --reviewer REVIEWER --reason REASON --output APPROVAL_JSON`
   - Add `--match-record MATCH_JSON` when the proposal came from a remote source.
   - `--manual-match-override` is valid only after explicit review of a non-accepted match.
   - Approval binds the exact proposal and the current whole-file and lyric hashes.
   - Record the authorization already present in the user's request in `--reason`; `--reviewer` identifies who performed the review. Creating this record does not imply a second user confirmation or authorize a different change.

10. `backup --audio AUDIO_FILE --backup BACKUP_FILE --output BACKUP_JSON`
    - The destination must not already exist.
    - The backup must have a different `(st_dev, st_ino)` identity, not be a symlink, and have identical size and whole-file hash. Check the supplied path for symlinks before resolving it.

11. `write --audio AUDIO_FILE --proposal PROPOSAL_JSON --approval APPROVAL_JSON --backup BACKUP_FILE --output WRITE_JSON`
    - Refuses stale approvals, mismatched proposals, non-independent backups, or invalid synchronized lyrics.
    - Immediately performs the same checks as `verify`: lyrics, logical non-lyric tags, artwork, audio payload, streams, format, backup integrity, LRC structure when applicable, and residual content.
    - Restores the backup if an immediate verification check fails.
    - `passed: true` satisfies routine post-write verification. An immediate second full verification is unnecessary.

12. `verify --audio AUDIO_FILE --baseline BASELINE_JSON --proposal PROPOSAL_JSON --backup BACKUP_FILE --output VERIFY_JSON`
    - `--backup` is optional for read-only checks but required for a complete post-write audit.
    - Use for independent, later, or explicitly requested verification. It is not a mandatory final step for other operations.

13. `report --audio AUDIO_FILE --record RECORD_JSON --json-output AUDIT_JSON --markdown-output AUDIT_MD`
    - Repeat `--record` only for records belonging to this same audio file.
    - Produces one JSON object and one Markdown report for the track; it does not append to a library report.

The `inspect`, `write`, and `verify` subcommands accept explicit `--ffmpeg` and `--ffprobe` executable names or paths. No other configuration is read from environment variables.
