"""Exercise archive integrity with temporary files and in-memory HTTP responses."""

import http.client
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("download_bookmarks", SCRIPTS / "download_twitter_bookmarks.py")
download = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = download
spec.loader.exec_module(download)
spec = importlib.util.spec_from_file_location("validate_migrated_bookmarks", SCRIPTS / "clear_twitter_bookmarks.py")
clear = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clear)


def response(body, *, status=200, headers=()):
    """Use the actual HTTP reader, which permits short sized reads at EOF."""
    raw = f"HTTP/1.1 {status} Fixture\r\n".encode()
    raw += b"".join(f"{name}: {value}\r\n".encode() for name, value in headers)
    raw += b"Connection: close\r\n\r\n" + body

    class Socket:
        def makefile(self, *args, **kwargs):
            return io.BytesIO(raw)

    result = http.client.HTTPResponse(Socket())
    result.begin()
    return result


class DownloadIntegrityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.target = self.root / "image.jpg"
        self.partial = self.root / "image.jpg.part"
        self.job = download.MediaJob("https://fixture.invalid/image.jpg", self.target, "1")
        self.target.write_bytes(b"previous complete image")
        network = patch.object(download.urllib.request, "urlopen", side_effect=AssertionError("No network access"))
        self.urlopen = network.start()
        self.addCleanup(network.stop)
        sleeper = patch.object(download.time, "sleep")
        sleeper.start()
        self.addCleanup(sleeper.stop)

    def run_download(self, responses, retries=0):
        self.urlopen.side_effect = responses
        return download.download_one(self.job, refresh=True, timeout=1, retries=retries)[1]

    def test_truncated_response_preserves_existing_media(self):
        status = self.run_download([response(b"abc", headers=[("Content-Length", "10")])])
        self.assertTrue(status.startswith("error:"), status)
        self.assertEqual(self.target.read_bytes(), b"previous complete image")
        self.assertEqual(self.partial.read_bytes(), b"abc")

    def test_retry_resumes_a_truncated_response(self):
        status = self.run_download([
            response(b"abc", headers=[("Content-Length", "10")]),
            response(b"defghij", status=206, headers=[("Content-Length", " 7 "), ("Content-Range", " bytes 3-9/10 ")]),
        ], retries=1)
        self.assertEqual(status, "downloaded")
        self.assertEqual(self.target.read_bytes(), b"abcdefghij")
        self.assertFalse(self.partial.exists())
        self.assertEqual(self.urlopen.call_args_list[1].args[0].get_header("Range"), "bytes=3-")

    def test_invalid_or_incomplete_ranges_preserve_existing_media(self):
        cases = [
            ("missing range", [], b"def"),
            ("wrong offset", [("Content-Range", "bytes 0-2/3")], b"abc"),
            ("invalid total", [("Content-Range", "bytes 3-5/5")], b"def"),
            ("unknown total", [("Content-Range", "bytes 3-5/*")], b"def"),
            ("unfinished range", [("Content-Range", "bytes 3-5/10")], b"def"),
            ("truncated range", [("Content-Range", "bytes 3-9/10"), ("Content-Length", "7")], b"def"),
            ("conflicting length", [("Content-Range", "bytes 3-9/10"), ("Content-Length", "3")], b"def"),
        ]
        for name, headers, body in cases:
            with self.subTest(name=name):
                self.partial.write_bytes(b"abc")
                self.target.write_bytes(b"previous complete image")
                status = self.run_download([response(body, status=206, headers=headers)])
                self.assertTrue(status.startswith("error:"), status)
                self.assertEqual(self.target.read_bytes(), b"previous complete image")

    def test_full_response_restarts_a_partial_download(self):
        self.partial.write_bytes(b"stale bytes")
        status = self.run_download([response(b"new image", headers=[("Content-Length", "9")])])
        self.assertEqual(status, "downloaded")
        self.assertEqual(self.target.read_bytes(), b"new image")
        self.assertFalse(self.partial.exists())

    def test_unsatisfiable_range_retries_the_complete_file(self):
        self.partial.write_bytes(b"stale bytes")
        status = self.run_download([
            urllib.error.HTTPError(self.job.url, 416, "range not satisfiable", {"Content-Range": "bytes */9"}, None),
            response(b"new image", headers=[("Content-Length", "9")]),
        ], retries=1)
        self.assertEqual(status, "downloaded")
        self.assertEqual(self.target.read_bytes(), b"new image")
        self.assertIsNone(self.urlopen.call_args_list[1].args[0].get_header("Range"))

    def test_broken_chunked_stream_is_a_download_failure(self):
        status = self.run_download([response(b"5\r\nabc", headers=[("Transfer-Encoding", "chunked")])])
        self.assertTrue(status.startswith("error:"), status)
        self.assertEqual(self.target.read_bytes(), b"previous complete image")


class MigrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.media = self.root / "media"
        self.metadata = self.root / "metadata"
        self.old = self.media / "items" / "1" / "image.jpg"
        self.old.parent.mkdir(parents=True)
        self.old.write_bytes(b"ORIGINAL")
        self.target = self.media / "tweet-1-01.jpg"
        self.records = [{"id": "1", "media": [{"type": "photo", "url": "https://fixture.invalid/image.jpg", "localPath": "items/1/image.jpg"}]}]
        network = patch.object(download, "_load_twitter_cli", side_effect=AssertionError("No live X access"))
        self.loader = network.start()
        self.addCleanup(network.stop)

    def test_same_size_conflict_preserves_both_files(self):
        self.target.write_bytes(b"CONFLICT")
        with self.assertRaises(RuntimeError):
            download._flatten_record_media(self.media, "1", self.records[0])
        self.assertEqual(self.old.read_bytes(), b"ORIGINAL")
        self.assertEqual(self.target.read_bytes(), b"CONFLICT")
        self.assertEqual(self.records[0]["media"][0]["localPath"], "items/1/image.jpg")

    def test_identical_files_can_finish_an_interrupted_migration(self):
        self.target.write_bytes(b"ORIGINAL")
        self.assertEqual(download._flatten_record_media(self.media, "1", self.records[0]), 1)
        self.assertFalse(self.old.exists())
        self.assertEqual(self.target.read_bytes(), b"ORIGINAL")
        self.assertEqual(self.records[0]["media"][0]["localPath"], self.target.name)

    def test_public_migration_updates_media_root_for_separated_metadata(self):
        (self.media / "bookmarks.json").write_text(json.dumps(self.records))
        manifest = {
            "complete": True, "bookmarkFetchComplete": True, "mediaComplete": True,
            "mediaFailed": 0, "layout": "items", "bookmarkCount": 1,
            "mediaCount": 1, "mediaRoot": ".",
        }
        (self.media / "manifest.json").write_text(json.dumps(manifest))
        self.assertEqual(download.main([
            "--output", str(self.media), "--metadata-output", str(self.metadata), "--flatten-existing",
        ]), 0)
        self.loader.assert_not_called()
        self.assertEqual(clear.validate_archive(self.metadata)[1], {"1"})
        self.assertEqual(self.target.read_bytes(), b"ORIGINAL")


if __name__ == "__main__":
    unittest.main()
