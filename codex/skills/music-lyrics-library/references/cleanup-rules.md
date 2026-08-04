# Lyric cleaning contract

Apply these rules conservatively and log every removal or transformation.

- Remove credit/production/instrumentalist lines (`角色：人名`, `X by 人名`, producer, mixed by, studio, label, copyright, ISRC, OP/SP, and similar).
- Remove platform watermarks, advertising, links, payment/VIP prompts, source notices, and authorization boilerplate.
- Remove pure-music placeholders such as `纯音乐，请欣赏` when there is no lyric body.
- Remove isolated section labels (`[Intro]`, `[Verse]`, `[Chorus]`), standalone timestamps, numbered markers, inline LRC timestamps, and transcription terminators such as `--end--`.
- Remove title residue (`歌名-乐队名`) only when context confirms it is a heading, not a lyric line. Preserve explicitly identified foreign-language headers or title lines when they are part of the source text.
- Remove meaningless alphabet or pinyin runs and explanatory concert/program notes.
- For role-prefixed spoken lines (`童：`, `旁白：`, etc.), remove only the role prefix and retain the spoken lyric. Delete empty role-only or instrumental parenthetical lines; retain parenthesized lyric text that carries actual words.
- Keep foreign-language lyric text unchanged; do not translate. Normalize Unicode/whitespace without changing wording.

For segmentation, use source LRC gaps, repeated chorus structure, and recognizable verse/bridge boundaries. If a source is one giant paragraph, insert blank lines at musically defensible boundaries and record the reason. Never claim a paragraph split is source-authenticated when it was inferred.
