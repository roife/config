"""Check the archive/quality contract with local video and real FFmpeg tools."""

import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("upgrade_bookmark_quality", SCRIPTS / "upgrade_twitter_media_quality.py")
upgrade = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = upgrade
spec.loader.exec_module(upgrade)
spec = importlib.util.spec_from_file_location("validate_quality_report", SCRIPTS / "clear_twitter_bookmarks.py")
clear = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clear)
spec = importlib.util.spec_from_file_location("archive_quality_fixture", SCRIPTS / "download_twitter_bookmarks.py")
download = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = download
spec.loader.exec_module(download)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg and FFprobe are required for video integration tests")
class QualityReportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.media, self.metadata = self.root / "media", self.root / "metadata"
        self.paths = ["tweet-1-01.mp4", "tweet-2-quoted-01.mp4"]
        fixture = self.root / "fixture.mp4"
        subprocess.run([
            shutil.which("ffmpeg"), "-nostdin", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=32x32:r=1", "-t", "1",
            "-c:v", "mpeg4", "-q:v", "5", "-an", str(fixture),
        ], check=True, capture_output=True)
        self.video_bytes = fixture.read_bytes()
        video = SimpleNamespace(type="video", url="https://video.twimg.com/ext_tw_video/123/pu/vid/clip.mp4")
        author = SimpleNamespace(screen_name="fixture")
        first = SimpleNamespace(id="1", author=author, media=[video], quoted_tweet=None)
        second = SimpleNamespace(id="2", author=author, media=[], quoted_tweet=first)
        self.client = MagicMock()
        self.client.fetch_bookmarks.return_value = [first, second]
        cli = ModuleType("twitter_cli")
        serializer = ModuleType("twitter_cli.serialization")
        serializer.tweet_to_dict = lambda tweet: {
            "id": tweet.id, "text": "Local fixture", "author": {"screenName": "fixture"},
            "media": [{"type": media.type, "url": media.url} for media in tweet.media],
        }
        cli.serialization = serializer
        modules = patch.dict(sys.modules, {"twitter_cli": cli, "twitter_cli.serialization": serializer})
        modules.start()
        self.addCleanup(modules.stop)
        loader = patch.object(download, "_load_twitter_cli", return_value=(
            lambda: {"auth_token": "fixture", "ct0": "fixture"},
            lambda *args, **kwargs: self.client, dict, "fixture",
        ))
        loader.start()
        self.addCleanup(loader.stop)
        no_clear = patch.object(clear, "load_twitter_cli", side_effect=AssertionError("No live X access"))
        self.clear_loader = no_clear.start()
        self.addCleanup(no_clear.stop)
        no_network = patch.object(download.urllib.request, "urlopen", side_effect=AssertionError("No network access"))
        self.urlopen = no_network.start()
        self.addCleanup(no_network.stop)

    def archive(self, *, truncate=False, extra=()):
        body = self.video_bytes[:10] if truncate else self.video_bytes
        length = len(self.video_bytes)

        class Response(io.BytesIO):
            status = 200

            def getheader(self, name):
                return str(length) if name == "Content-Length" else None

        self.urlopen.side_effect = lambda *args, **kwargs: Response(body)
        return download.main([
            "--output", str(self.media), "--metadata-output", str(self.metadata),
            "--jobs", "1", "--retries", "0", *extra,
        ])

    def upgrade(self, *, invalid_video=False):
        def download_candidate(*args, **kwargs):
            (self.media / ".hq-123.mp4").write_bytes(b"invalid video" if invalid_video else self.video_bytes)
            return 0

        with patch.object(upgrade, "ensure_runtime", return_value=("mock-yt-dlp", shutil.which("ffprobe"))), \
                patch.object(upgrade, "run_ytdlp", side_effect=download_candidate):
            return upgrade.main(["--output", str(self.media), "--metadata-output", str(self.metadata)])

    def test_produced_report_matches_media_and_rejects_a_later_replacement(self):
        self.assertEqual(self.archive(), 0)
        self.assertEqual(self.upgrade(), 0)
        self.assertEqual(clear.main(["--metadata", str(self.metadata), "--validate-only"]), 0)
        self.clear_loader.assert_not_called()
        report = json.loads((self.metadata / "highest-resolution-report.json").read_text())
        self.assertEqual((report["videoReferences"], report["uniqueMedia"]), (2, 1))
        for name in self.paths:
            self.assertEqual((self.media / name).read_bytes(), self.video_bytes)
        (self.media / self.paths[0]).write_bytes(b"changed since quality validation")
        with self.assertRaises(ValueError):
            clear.validate_archive(self.metadata)

    def test_failed_archive_cannot_report_complete(self):
        self.assertEqual(self.archive(truncate=True), 2)
        manifest = json.loads((self.metadata / "manifest.json").read_text())
        self.assertFalse(manifest["complete"])
        self.assertFalse(manifest["mediaComplete"])
        self.assertEqual(manifest["mediaFailed"], 2)
        self.assertEqual(clear.main(["--metadata", str(self.metadata)]), 1)
        self.clear_loader.assert_not_called()

    def test_invalid_upgrade_preserves_media_and_blocks_validation(self):
        self.assertEqual(self.archive(), 0)
        self.assertEqual(self.upgrade(invalid_video=True), 2)
        for name in self.paths:
            self.assertEqual((self.media / name).read_bytes(), self.video_bytes)
        report = json.loads((self.metadata / "highest-resolution-report.json").read_text())
        self.assertFalse(report["complete"])
        self.assertEqual(report["failedReferences"], 2)
        self.assertEqual(clear.main(["--metadata", str(self.metadata)]), 1)
        self.clear_loader.assert_not_called()

    def test_metadata_export_and_capped_fetch_remain_incomplete(self):
        self.assertEqual(self.archive(extra=["--metadata-only"]), 2)
        self.urlopen.assert_not_called()
        manifest = json.loads((self.metadata / "manifest.json").read_text())
        self.assertTrue(manifest["bookmarkFetchComplete"])
        self.assertFalse(manifest["complete"])
        self.assertEqual(self.archive(extra=["--max-bookmarks", "2"]), 2)
        manifest = json.loads((self.metadata / "manifest.json").read_text())
        self.assertFalse(manifest["bookmarkFetchComplete"])
        self.assertTrue(manifest["mediaComplete"])
        self.assertFalse(manifest["complete"])


if __name__ == "__main__":
    unittest.main()
