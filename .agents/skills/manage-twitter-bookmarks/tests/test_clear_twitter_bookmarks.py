"""Local fixtures only: never authenticate or contact X."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "clear_twitter_bookmarks.py"
spec = importlib.util.spec_from_file_location("clear_bookmarks", SCRIPT)
clear = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clear)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.media = self.root / "media"
        self.metadata = self.root / "metadata"
        self.media.mkdir()
        self.metadata.mkdir()
        (self.media / "image.jpg").write_bytes(b"local fixture")
        self.records = [{"id": "1", "media": [{"type": "photo", "localPath": "image.jpg"}]}]
        self.manifest = {
            "complete": True,
            "bookmarkFetchComplete": True,
            "mediaComplete": True,
            "mediaFailed": 0,
            "layout": "flat",
            "bookmarkCount": 1,
            "mediaCount": 1,
            "mediaRoot": "../media",
        }
        self.write_archive()
        loader = patch.object(clear, "load_twitter_cli", side_effect=AssertionError("No live X access"))
        self.loader = loader.start()
        self.addCleanup(loader.stop)

    def write_json(self, name, value):
        (self.metadata / name).write_text(json.dumps(value))

    def write_archive(self):
        self.write_json("bookmarks.json", self.records)
        self.write_json("manifest.json", self.manifest)

    def run_clear(self, live=None, final=None, removal_error=None, extra=()):
        client = MagicMock()
        client.fetch_bookmarks.side_effect = [
            [SimpleNamespace(id=value) for value in (live if live is not None else ["1"])],
            final if isinstance(final, Exception) else [SimpleNamespace(id=value) for value in (final or [])],
        ]

        def remove(tweet_id):
            snapshot = json.loads((self.metadata / "pre-clear-bookmarks.json").read_text())
            self.assertIn(tweet_id, [tweet["id"] for tweet in snapshot["bookmarks"]])
            if removal_error:
                raise removal_error

        client.unbookmark_tweet.side_effect = remove
        self.loader.side_effect = None
        self.loader.return_value = (
            lambda: {"auth_token": "fixture", "ct0": "fixture"},
            lambda *args, **kwargs: client,
            lambda: {},
            lambda tweet: {"id": tweet.id},
            "fixture",
        )
        status = clear.main(["--metadata", str(self.metadata), *extra])
        report_path = self.metadata / "clear-bookmarks-report.json"
        report = json.loads(report_path.read_text()) if report_path.exists() else None
        return status, report, client

    def test_validate_only_neither_authenticates_nor_writes(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(clear, "atomic_write_json") as writer:
            self.assertEqual(clear.main(["--metadata", str(self.metadata), "--validate-only"]), 0)
        self.loader.assert_not_called()
        writer.assert_not_called()
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_incomplete_archive_is_rejected_before_authentication(self):
        self.manifest["bookmarkFetchComplete"] = False
        self.write_archive()
        self.assertEqual(clear.main(["--metadata", str(self.metadata)]), 1)
        self.loader.assert_not_called()

    def test_invalid_layout_entries_are_rejected(self):
        for name, data in [("debug.log", b"log"), ("data.json", b"{}"), ("empty.jpg", b""), ("partial.mp4.part", b"part")]:
            with self.subTest(name=name):
                entry = self.media / name
                entry.write_bytes(data)
                with self.assertRaises(ValueError):
                    clear.validate_archive(self.metadata)
                entry.unlink()
        nested = self.media / "nested.jpg"
        nested.mkdir()
        with self.assertRaises(ValueError):
            clear.validate_archive(self.metadata)

    def test_missing_declared_media_is_rejected(self):
        (self.media / "image.jpg").unlink()
        with self.assertRaises(ValueError):
            clear.validate_archive(self.metadata)

    def test_media_cannot_escape_target(self):
        outside = self.root / "outside.jpg"
        outside.write_bytes(b"outside")
        link = self.media / "image.jpg"
        link.unlink()
        link.symlink_to(outside)
        with self.assertRaises(ValueError):
            clear.validate_archive(self.metadata)

    def test_video_requires_complete_matching_quality_report(self):
        (self.media / "image.jpg").rename(self.media / "video.mp4")
        self.records[0]["media"] = [{"type": "video", "localPath": "video.mp4"}]
        self.write_archive()
        with self.assertRaises(ValueError):
            clear.validate_archive(self.metadata)
        quality = {"complete": True, "ytDlpExitCode": 0, "videoReferences": 1, "replacedReferences": 1, "failedReferences": 0}
        self.write_json("highest-resolution-report.json", quality)
        self.assertEqual(clear.validate_archive(self.metadata)[1], {"1"})
        for key, value in [("complete", False), ("videoReferences", 2), ("replacedReferences", 0), ("failedReferences", 1)]:
            with self.subTest(key=key):
                self.write_json("highest-resolution-report.json", {**quality, key: value})
                with self.assertRaises(ValueError):
                    clear.validate_archive(self.metadata)

    def test_success_snapshots_before_removal_and_preserves_media(self):
        status, report, client = self.run_clear()
        self.assertEqual(status, 0)
        self.assertTrue(report["complete"])
        self.assertEqual(report["remaining"], 0)
        self.assertEqual(report["failed"], [])
        client.unbookmark_tweet.assert_called_once_with("1")
        self.assertEqual((self.media / "image.jpg").read_bytes(), b"local fixture")

    def test_failed_final_fetch_reports_unknown(self):
        status, report, _ = self.run_clear(final=RuntimeError("fetch unavailable"))
        self.assertEqual(status, 2)
        self.assertFalse(report["complete"])
        self.assertIsNone(report["remaining"])
        self.assertIsNone(report["remainingIds"])
        self.assertEqual(report["verificationError"], "fetch unavailable")

    def test_removal_error_prevents_completion_even_when_empty(self):
        status, report, _ = self.run_clear(removal_error=RuntimeError("write failed"))
        self.assertEqual(status, 2)
        self.assertFalse(report["complete"])
        self.assertEqual(report["remaining"], 0)
        self.assertEqual(len(report["failed"]), 1)

    def test_unarchived_bookmark_blocks_all_removals(self):
        status, _, client = self.run_clear(live=["1", "2"])
        self.assertEqual(status, 3)
        client.unbookmark_tweet.assert_not_called()

    def test_allow_unarchived_does_not_bypass_fetch_cap(self):
        status, _, client = self.run_clear(live=["2"], extra=["--max-bookmarks", "1", "--allow-unarchived"])
        self.assertEqual(status, 3)
        client.unbookmark_tweet.assert_not_called()


if __name__ == "__main__":
    unittest.main()
