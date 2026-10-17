# /// script
# requires-python = ">=3.12"
# dependencies = ["mutagen>=1.47,<2"]
# ///
"""Run with uv; all audio fixtures are synthesized in temporary directories."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/music_track_lyrics.py"
spec = importlib.util.spec_from_file_location("music_track_lyrics", SCRIPT)
lyrics = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lyrics
spec.loader.exec_module(lyrics)

LINE = "I am a VIP tonight"
EXCEPTIONS = {LINE: "Reviewed in context as a sung lyric."}


class TrackLyricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixtures.cleanup)
        for extension, codec in (("m4a", "aac"), ("mp3", "libmp3lame")):
            subprocess.run(
                [
                    "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=2", "-c:a", codec,
                    "-metadata", "title=Fixture", "-metadata", "artist=Test",
                    str(Path(cls.fixtures.name) / f"track.{extension}"),
                ],
                check=True,
            )

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name).resolve()

    def audio(self, extension):
        target = self.directory / f"track.{extension}"
        shutil.copy2(Path(self.fixtures.name) / target.name, target)
        return target

    def save(self, name, value):
        target = self.directory / name
        target.write_text(json.dumps(value), encoding="utf-8")
        return target

    def command(self, audio, command, *arguments):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), command, "--audio", str(audio),
             *map(str, arguments)],
            check=True, capture_output=True, text=True,
        )
        return json.loads(result.stdout)

    def approve(self, audio, proposal):
        return lyrics.approve_change(
            audio, proposal, None, "accept", "test", "Authorized fixture edit", False
        )

    def source(self, audio, **changes):
        source = {
            "provider": "lrclib", "source_id": "1", "title": "Fixture",
            "artists": ["Test"], "duration": 2, "instrumental": False,
        }
        source.update(changes)
        return {"audio_path": str(audio), "source": source}

    def test_lrclib_explicit_query_replaces_metadata_search(self):
        audio = self.audio("m4a")
        payload = [{
            "id": 7, "trackName": "Corrected title", "artistName": "Test",
            "duration": 2, "plainLyrics": "A lyric",
        }]
        for query, expected in (
            (None, {"track_name": ["Fixture"], "artist_name": ["Test"]}),
            ("Corrected title Test", {"q": ["Corrected title Test"]}),
        ):
            with self.subTest(query=query):
                with patch.object(lyrics.urllib.request, "urlopen") as urlopen:
                    urlopen.return_value.__enter__.return_value.read.return_value = (
                        json.dumps(payload).encode("utf-8")
                    )
                    result = lyrics.search_source(
                        audio, "lrclib", "https://example.invalid/search", query,
                        10, 15, "fixture-test",
                    )
                requested = urlopen.call_args.args[0].full_url
                self.assertEqual(
                    urllib.parse.parse_qs(urllib.parse.urlsplit(requested).query),
                    expected,
                )
                self.assertEqual(result["requested_url"], requested)
                self.assertEqual(result["candidates"][0]["plain_lyrics"], "A lyric")

    def test_manual_match_override_cannot_accept_known_mismatch(self):
        audio = self.audio("m4a")
        proposal = lyrics.clean_track_lyrics(audio, "A lyric")
        for changes in (
            {"title": "Fixture (Live)"}, {"artists": ["Different performer"]},
            {"duration": 999}, {"instrumental": True},
        ):
            with self.subTest(changes=changes):
                matched = lyrics.match_source(audio, self.source(audio, **changes), {}, 1)
                self.assertFalse(matched["accepted"])
                with self.assertRaisesRegex(ValueError, "known.*mismatch"):
                    lyrics.approve_change(
                        audio, proposal, matched, "accept", "test",
                        "Reviewed source, but it is a different recording.", True,
                    )
                rejected = lyrics.approve_change(
                    audio, proposal, matched, "reject", "test", "Wrong recording", False
                )
                self.assertEqual(rejected["decision"], "reject")

    def test_manual_match_override_requires_reason_for_missing_evidence(self):
        audio = self.audio("m4a")
        proposal = lyrics.clean_track_lyrics(audio, "A lyric")
        matched = lyrics.match_source(audio, self.source(audio, duration=0), {}, 1)
        self.assertFalse(matched["accepted"])
        with self.assertRaisesRegex(ValueError, "explicit override"):
            lyrics.approve_change(
                audio, proposal, matched, "accept", "test", "Checked", False
            )
        for reason in ("", " \t\n"):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, "reason"):
                lyrics.approve_change(
                    audio, proposal, matched, "accept", "test", reason, True
                )
        approved = lyrics.approve_change(
            audio, proposal, matched, "accept", "test",
            "Confirmed recording from the source identifier; duration is unavailable.",
            True,
        )
        self.assertEqual(approved["decision"], "accept")
        self.assertEqual(
            approved["match_record_sha256"], lyrics.canonical_json_sha256(matched)
        )

    def test_source_match_must_describe_current_recording(self):
        for tag, replacement in (
            ("©nam", "Fixture (Live)"), ("©ART", "Different performer")
        ):
            with self.subTest(tag=tag):
                audio = self.audio("m4a")
                proposal = lyrics.clean_track_lyrics(audio, "A lyric")
                matched = lyrics.match_source(audio, self.source(audio), {}, 1)
                approved = lyrics.approve_change(
                    audio, proposal, matched, "accept", "test", "Reviewed", False
                )
                self.assertEqual(approved["decision"], "accept")
                changed = lyrics.load_audio(audio)
                changed.tags[tag] = [replacement]
                changed.save()
                for manual_override in (False, True):
                    with (
                        self.subTest(manual_override=manual_override),
                        self.assertRaisesRegex(ValueError, "stale.*match again"),
                    ):
                        lyrics.approve_change(
                            audio, proposal, matched, "accept", "test",
                            "Reviewed", manual_override,
                        )
                rejected = lyrics.approve_change(
                    audio, proposal, matched, "reject", "test", "Stale match", False
                )
                self.assertEqual(rejected["decision"], "reject")

    def test_alignment_rejects_invalid_override_seconds(self):
        audio = self.audio("m4a")
        for seconds in (-100, float("nan"), float("inf"), float("-inf")):
            with (
                self.subTest(seconds=seconds),
                self.assertRaisesRegex(ValueError, "finite.*nonnegative"),
            ):
                lyrics.align_track_lyrics(
                    audio, "A lyric", "[00:01.000]A lyric", 0.9, 2,
                    {"0": seconds},
                )
        zero = lyrics.align_track_lyrics(
            audio, "A lyric", "[00:01.000]A lyric", 0.9, 2, {"0": 0}
        )
        self.assertEqual(zero["status"], "ready")
        self.assertEqual(zero["lyrics"], "[00:00.000]A lyric")
        late = lyrics.align_track_lyrics(
            audio, "A lyric", "[00:01.000]A lyric", 0.9, 2, {"0": 10}
        )
        self.assertEqual(late["status"], "review")
        self.assertFalse(late["validation"]["within_duration"])

    def test_alignment_rejects_invalid_override_indexes(self):
        audio = self.audio("m4a")
        for index in ("-1", "1"):
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "line index"):
                lyrics.align_track_lyrics(
                    audio, "A lyric", "[00:01.000]A lyric", 0.9, 2,
                    {index: 0.5},
                )

    def test_vip_detection_preserves_words_containing_the_letters(self):
        audio = self.audio("m4a")
        lines = "The viper danced\nA Viper appeared\nWe are reviving hope"
        proposal = lyrics.clean_track_lyrics(audio, lines)
        self.assertEqual(proposal["lyrics"], lines)
        self.assertEqual(proposal["residual_flags"], [])
        for promotion in ("VIP only", "开通VIP", "VIP会员", "限时VIP福利"):
            with self.subTest(promotion=promotion):
                flagged = lyrics.clean_track_lyrics(audio, promotion)
                self.assertEqual(flagged["lyrics"], "")
                self.assertIn("promotion_or_source_notice", lyrics.residual_flags(promotion))
        reviewed = lyrics.clean_track_lyrics(audio, LINE, lyric_exceptions=EXCEPTIONS)
        self.assertEqual(reviewed["lyrics"], LINE)
        self.assertEqual(reviewed["residual_flags"], [])

    def test_cli_exceptions_survive_composition_and_write(self):
        for extension in ("m4a", "mp3"):
            for timed in (False, True):
                with self.subTest(extension=extension, timed=timed):
                    audio = self.audio(extension)
                    original = audio.read_bytes()
                    raw = self.directory / "input.txt"
                    raw.write_text(
                        f"{LINE}\nAnother lyric\nhttps://example.invalid/promo\n",
                        encoding="utf-8",
                    )
                    exceptions = self.save("exceptions.json", EXCEPTIONS)
                    cleaned = self.command(
                        audio, "clean", "--lyrics", raw,
                        "--lyric-exceptions", exceptions,
                    )
                    self.assertEqual(cleaned["lyrics"], f"{LINE}\nAnother lyric")
                    self.assertEqual(cleaned["residual_flags"], [])
                    # A second clean must retain the reviewed lines from its JSON input.
                    cleaned = self.command(
                        audio, "clean", "--lyrics", self.save("clean.json", cleaned)
                    )
                    segmented = self.command(
                        audio, "segment", "--lyrics", self.save("clean.json", cleaned),
                        "--gap-seconds", 2, "--break-before", 2,
                    )
                    self.assertEqual(segmented["lyrics"], f"{LINE}\n\nAnother lyric")
                    proposal = segmented
                    if timed:
                        source = self.directory / "source.lrc"
                        source.write_text(
                            f"[00:00.100]{LINE}\n[00:01.000]Another lyric\n",
                            encoding="utf-8",
                        )
                        proposal = self.command(
                            audio, "align", "--lyrics", self.save("segment.json", segmented),
                            "--timed-source", source, "--minimum-similarity", 0.9,
                            "--split-window-seconds", 2,
                        )
                        self.assertEqual(proposal["status"], "ready")
                    self.assertEqual(proposal["lyric_exceptions"], EXCEPTIONS)
                    proposal_path = self.save("proposal.json", proposal)
                    approval = self.command(
                        audio, "approve", "--proposal", proposal_path,
                        "--decision", "accept", "--reviewer", "test",
                        "--reason", "Authorized fixture edit; reviewed the exact lyric line",
                    )
                    backup = self.directory / f"backup-{timed}.{extension}"
                    self.command(audio, "backup", "--backup", backup)
                    result = self.command(
                        audio, "write", "--proposal", proposal_path,
                        "--approval", self.save("approval.json", approval),
                        "--backup", backup,
                    )
                    self.assertTrue(result["passed"])
                    self.assertTrue(all(result["checks"].values()))
                    self.assertEqual(result["after"]["lyrics"], proposal["lyrics"])
                    self.assertEqual(backup.read_bytes(), original)
                    verified = self.command(
                        audio, "verify", "--proposal", proposal_path,
                        "--baseline", self.save("baseline.json", result["baseline"]),
                        "--backup", backup,
                    )
                    self.assertTrue(verified["passed"])

    def test_invalid_exceptions_and_wrong_track_are_rejected(self):
        audio = self.audio("m4a")
        for exceptions in ({LINE: ""}, {"VIP": "Only a substring"},
                           {"Unrelated line": "Stale"}, [LINE], {"": "Empty"}):
            with self.subTest(exceptions=exceptions):
                with self.assertRaises((TypeError, ValueError)):
                    lyrics.clean_track_lyrics(audio, LINE, lyric_exceptions=exceptions)
        proposal = lyrics.clean_track_lyrics(audio, LINE, lyric_exceptions=EXCEPTIONS)
        record = self.save("wrong-track.json", proposal)
        with self.assertRaises(ValueError):
            lyrics.read_lyrics_input(str(record), ("lyrics",), self.audio("mp3"))

    def test_exception_changes_invalidate_approval(self):
        audio = self.audio("m4a")
        proposal = lyrics.clean_track_lyrics(audio, LINE, lyric_exceptions=EXCEPTIONS)
        approval = self.approve(audio, proposal)
        backup = self.directory / "backup.m4a"
        lyrics.backup_track(audio, backup)
        changed = copy.deepcopy(proposal)
        changed["lyric_exceptions"][LINE] = "Changed review reason"
        with self.assertRaisesRegex(ValueError, "approval does not bind"):
            lyrics.write_track_lyrics(audio, changed, approval, backup, "ffmpeg", "ffprobe")
        self.assertEqual(audio.read_bytes(), backup.read_bytes())

    def test_unreviewed_similar_line_still_triggers_rollback(self):
        for extension in ("m4a", "mp3"):
            with self.subTest(extension=extension):
                audio = self.audio(extension)
                proposal = lyrics.clean_track_lyrics(audio, LINE, lyric_exceptions=EXCEPTIONS)
                proposal["lyrics"] += "\nI am a VIP tomorrow"
                approval = self.approve(audio, proposal)
                backup = self.directory / f"backup.{extension}"
                lyrics.backup_track(audio, backup)
                with self.assertRaisesRegex(RuntimeError, "post-write verification failed"):
                    lyrics.write_track_lyrics(audio, proposal, approval, backup, "ffmpeg", "ffprobe")
                self.assertEqual(audio.read_bytes(), backup.read_bytes())

    def test_exceptions_cannot_bypass_metadata_checks(self):
        audio = self.audio("m4a")
        proposal = lyrics.clean_track_lyrics(audio, LINE, lyric_exceptions=EXCEPTIONS)
        approval = self.approve(audio, proposal)
        backup = self.directory / "backup.m4a"
        lyrics.backup_track(audio, backup)
        real_write = lyrics.set_embedded_lyrics

        def corrupt_metadata(path, text):
            real_write(path, text)
            track = lyrics.load_audio(path)
            track.tags["©nam"] = ["Unexpected title"]
            track.save()

        with patch.object(lyrics, "set_embedded_lyrics", side_effect=corrupt_metadata):
            with self.assertRaisesRegex(RuntimeError, "post-write verification failed"):
                lyrics.write_track_lyrics(audio, proposal, approval, backup, "ffmpeg", "ffprobe")
        self.assertEqual(audio.read_bytes(), backup.read_bytes())

    def test_backup_corruption_is_still_rejected(self):
        audio = self.audio("mp3")
        proposal = lyrics.clean_track_lyrics(audio, "Ordinary lyric")
        approval = self.approve(audio, proposal)
        original = audio.read_bytes()
        backup = self.directory / "backup.mp3"
        result = lyrics.backup_track(audio, backup)
        self.assertEqual(result["whole_file_sha256"], lyrics.file_sha256(audio))
        with backup.open("ab") as stream:
            stream.write(b"corruption")
        with self.assertRaisesRegex(ValueError, "backup is not byte-identical"):
            lyrics.write_track_lyrics(audio, proposal, approval, backup, "ffmpeg", "ffprobe")
        self.assertEqual(audio.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
