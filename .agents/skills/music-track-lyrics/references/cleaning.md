# Lyric cleaning and classification contract

Apply transformations conservatively and retain the logged category, original line, and replacement when applicable.

- Remove production, performance-credit, studio, label, copyright, ISRC, OP/SP, and similar credit lines.
- Remove platform watermarks, advertising, links, payment prompts, source notices, and authorization boilerplate.
- Remove isolated section labels, standalone or inline LRC timestamps, numbered markers, and transcription terminators.
- Preserve title-matching lines unless context establishes that they are headings. Pass confirmed, one-based source-line numbers through `clean --heading-line` to remove matching headings; title equality alone is insufficient.
- Remove placeholder-only text such as a pure-music or unavailable-lyrics notice.
- For a role-prefixed spoken line, remove only the role prefix and preserve the spoken lyric. Remove an empty role-only marker.
- Preserve meaningful parenthesized lyric text and all foreign-language lyric text. Do not translate or rewrite wording.
- Normalize line endings, Unicode representation, surrounding whitespace, and repeated blank lines without altering words.

For segmentation, preserve existing paragraph breaks. Add a new break only from an explicit reviewed line number or a configured gap between synchronized events. Do not infer structure from plain text alone.

For classification, a non-placeholder lyric body is `lyrical`. Use `instrumental` only with affirmative source or user evidence. Otherwise classify a lyric-less track as `unresolved`. Classification does not authorize clearing existing lyrics; remove or replace them only within the requested change.
