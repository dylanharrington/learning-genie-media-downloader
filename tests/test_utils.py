"""Unit tests for utility functions."""

import json
import ssl
import sys
from collections import defaultdict
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestParseCurl:
    """Tests for fetch.parse_curl()"""

    def test_parse_simple_curl(self):
        from fetch import parse_curl

        curl = "curl 'https://api.example.com/data' -H 'Authorization: Bearer token123' -H 'Accept: application/json'"
        url, headers = parse_curl(curl)

        assert url == "https://api.example.com/data"
        assert headers["Authorization"] == "Bearer token123"
        assert headers["Accept"] == "application/json"

    def test_parse_curl_with_double_quotes(self):
        from fetch import parse_curl

        curl = 'curl "https://api.example.com/data" -H "QB-Token: abc123"'
        url, headers = parse_curl(curl)

        assert url == "https://api.example.com/data"
        assert headers["QB-Token"] == "abc123"

    def test_parse_curl_with_cookie_flag(self):
        from fetch import parse_curl

        curl = "curl 'https://api.example.com' -b 'session=xyz789'"
        url, headers = parse_curl(curl)

        assert url == "https://api.example.com"
        assert headers["Cookie"] == "session=xyz789"

    def test_parse_curl_no_headers(self):
        from fetch import parse_curl

        curl = "curl 'https://api.example.com/simple'"
        url, headers = parse_curl(curl)

        assert url == "https://api.example.com/simple"
        assert headers == {}


class TestTLSCompatibility:
    def test_normalizes_legacy_s3_double_slash_path(self):
        from tls_utils import normalized_request_url

        assert normalized_request_url(
            "https://s3.amazonaws.com//com.learning-genie.prod.us/photo.jpg"
        ) == "https://s3.amazonaws.com/com.learning-genie.prod.us/photo.jpg"

    def test_does_not_rewrite_other_hosts_or_paths(self):
        from tls_utils import normalized_request_url

        assert normalized_request_url("https://example.com//photo.jpg") == "https://example.com//photo.jpg"
        assert normalized_request_url("https://s3.amazonaws.com/bucket/photo.jpg") == (
            "https://s3.amazonaws.com/bucket/photo.jpg"
        )

    def test_quickblox_relaxes_only_strict_x509_checks(self):
        from tls_utils import verified_context_for_url

        context = verified_context_for_url("https://apilearninggenie.quickblox.com/chat/Dialog.json")
        assert context.check_hostname is True
        assert context.verify_mode == ssl.CERT_REQUIRED
        if hasattr(ssl, "VERIFY_X509_STRICT"):
            assert not context.verify_flags & ssl.VERIFY_X509_STRICT

    def test_learning_genie_api_also_relaxes_only_strict_x509_checks(self):
        from tls_utils import verified_context_for_url

        context = verified_context_for_url("https://api2.learning-genie.com/api/v1/Enrollments")
        assert context.check_hostname is True
        assert context.verify_mode == ssl.CERT_REQUIRED
        if hasattr(ssl, "VERIFY_X509_STRICT"):
            assert not context.verify_flags & ssl.VERIFY_X509_STRICT

    def test_unrelated_hosts_keep_default_strict_checks(self):
        from tls_utils import verified_context_for_url

        context = verified_context_for_url("https://example.com/")
        assert context.check_hostname is True
        assert context.verify_mode == ssl.CERT_REQUIRED
        if hasattr(ssl, "VERIFY_X509_STRICT"):
            assert context.verify_flags & ssl.VERIFY_X509_STRICT


class TestDownloadChatUtils:
    """Tests for scripts/download_chat.py utility functions"""

    def test_parse_iso_date(self):
        from download_chat import parse_iso_date

        assert parse_iso_date("2026-01-12T22:18:37Z") == "2026:01:12 14:18:37"
        assert parse_iso_date("2025-06-15T09:30:00Z") == "2025:06:15 02:30:00"
        assert parse_iso_date("") == ""
        assert parse_iso_date(None) == ""

    def test_is_thumbnail(self):
        from download_chat import is_thumbnail

        # Thumbnails end with hex + 'jpg' without a dot
        assert is_thumbnail("https://example.com/abc123jpg") is True
        assert is_thumbnail("https://example.com/deadbeef0jpg") is True

        # Regular files have .jpg extension
        assert is_thumbnail("https://example.com/photo.jpg") is False
        assert is_thumbnail("https://example.com/video.mp4") is False
        assert is_thumbnail("https://example.com/image.png") is False

    def test_get_file_type(self):
        from download_chat import get_file_type

        assert get_file_type("https://example.com/video.mp4") == "mp4"
        assert get_file_type("https://example.com/image.png") == "jpg"  # .png treated as jpg
        assert get_file_type("https://example.com/unknown.xyz") == "bin"

    def test_sanitize_folder_name(self):
        from download_chat import sanitize_folder_name

        assert sanitize_folder_name("John Doe") == "John_Doe"
        assert sanitize_folder_name("Bluey's Photos!") == "Bluey_s_Photos"
        assert sanitize_folder_name("Name  With   Spaces") == "Name_With_Spaces"
        assert sanitize_folder_name("__leading__") == "leading"

    def test_generate_filename_basic(self):
        from download_chat import generate_filename

        item = {
            "date_raw": "2026-01-12T22:18:37Z",
            "file_type": "jpg",
            "sender": "Ms. Teacher",
        }
        date_counts = defaultdict(int)

        filename = generate_filename(item, date_counts)
        assert filename == "Ms_Teacher_2026-01-12_22-18-37.jpg"

    def test_generate_filename_duplicate_timestamps(self):
        from download_chat import generate_filename

        item = {
            "date_raw": "2026-01-12T22:18:37Z",
            "file_type": "jpg",
            "sender": "Teacher",
        }
        date_counts = defaultdict(int)

        # First file
        f1 = generate_filename(item, date_counts)
        assert f1 == "Teacher_2026-01-12_22-18-37.jpg"

        # Second file with same timestamp
        f2 = generate_filename(item, date_counts)
        assert f2 == "Teacher_2026-01-12_22-18-37_02.jpg"

        # Third file
        f3 = generate_filename(item, date_counts)
        assert f3 == "Teacher_2026-01-12_22-18-37_03.jpg"


class TestTimeUtils:
    def test_utc_to_local_date_and_time(self):
        from time_utils import utc_to_local_date, utc_to_local_time, filename_utc_to_local_exif

        assert utc_to_local_date("2026-03-17T23:47:47Z") == "2026-03-17"
        assert utc_to_local_time("2026-03-17T23:47:47Z") == "16:47"
        assert filename_utc_to_local_exif("2026-03-17_23-47-47") == "2026:03:17 16:47:47"


class TestDownloadHomeUtils:
    """Tests for scripts/download_home.py utility functions"""

    def test_generate_filename_basic(self):
        from download_home import generate_filename

        item = {
            "child": "Bluey Heeler",
            "date": "2026-01-12 21:19:51",
            "fileType": "jpg",
        }
        date_counts = defaultdict(int)

        filename = generate_filename(item, date_counts)
        assert filename == "Bluey_Heeler_2026-01-12_21-19-51.jpg"

    def test_generate_filename_video(self):
        from download_home import generate_filename

        item = {
            "child": "Bingo Heeler",
            "date": "2026-01-12 15:30:00",
            "fileType": "mp4",
        }
        date_counts = defaultdict(int)

        filename = generate_filename(item, date_counts)
        assert filename == "Bingo_Heeler_2026-01-12_15-30-00.mp4"

    def test_generate_filename_duplicates(self):
        from download_home import generate_filename

        item = {
            "child": "Kid",
            "date": "2026-01-12 10:00:00",
            "fileType": "jpg",
        }
        date_counts = defaultdict(int)

        f1 = generate_filename(item, date_counts)
        f2 = generate_filename(item, date_counts)

        assert f1 == "Kid_2026-01-12_10-00-00.jpg"
        assert f2 == "Kid_2026-01-12_10-00-00_02.jpg"


class TestConfig:
    """Tests for config.py functions"""

    def test_load_config_missing_file(self, tmp_path, monkeypatch):
        import config

        # Point to non-existent config
        monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "nonexistent.json")

        result = config.load_config()
        assert result == {"location": None, "email": None, "bw_item": None, "op_path": None}

    def test_save_and_load_config(self, tmp_path, monkeypatch):
        import config

        config_file = tmp_path / "config.json"
        monkeypatch.setattr(config, "CONFIG_FILE", config_file)

        # Save config
        test_config = {"location": {"name": "Test School", "latitude": 37.0, "longitude": -122.0}}
        config.save_config(test_config)

        # Load it back
        loaded = config.load_config()
        assert loaded["location"]["name"] == "Test School"
        assert loaded["location"]["latitude"] == 37.0

    def test_load_config_merges_defaults(self, tmp_path, monkeypatch):
        import config

        config_file = tmp_path / "config.json"
        monkeypatch.setattr(config, "CONFIG_FILE", config_file)

        # Write partial config
        with open(config_file, "w") as f:
            json.dump({"custom_key": "value"}, f)

        loaded = config.load_config()
        # Should have both the custom key and the default location key
        assert loaded["custom_key"] == "value"
        assert "location" in loaded
