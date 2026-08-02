import re
import pytest
from main import SAFE_FILENAME
from security import create_document_token, validate_document_token, validate_public_https_url


class TestSafeFilename:
    """Test the filename regex used for path traversal prevention."""

    def test_valid_filenames(self):
        valid = [
            "cv_abc123.pdf",
            "cover_letter_x.pdf",
            "cv-2025.pdf",
            "my_cv_123.pdf",
        ]
        for name in valid:
            assert SAFE_FILENAME.match(name), f"Expected valid: {name}"

    def test_path_traversal_rejected(self):
        malicious = [
            "../etc/passwd.pdf",
            "..\\windows\\system32.pdf",
            "../../backend/.env.pdf",
            "cv/../../../etc/passwd.pdf",
            "cv\\\\..\\\\..\\\\etc\\\\passwd.pdf",
        ]
        for name in malicious:
            assert not SAFE_FILENAME.match(name), f"Should reject: {name}"

    def test_special_chars_rejected(self):
        attacks = [
            "cv;rm -rf /.pdf",
            "cv`whoami`.pdf",
            "cv$(whoami).pdf",
            "cv.jpg.pdf",
            "cv.pdf;echo pwned",
        ]
        for name in attacks:
            assert not SAFE_FILENAME.match(name), f"Should reject: {name}"

    def test_non_pdf_rejected(self):
        names = ["file.txt", "file.html", "file.exe", "file"]
        for name in names:
            assert not SAFE_FILENAME.match(name), f"Should reject: {name}"


class TestDocumentTokens:
    def test_token_is_scoped_to_filename(self):
        token = create_document_token(["cv_abc.pdf"])
        assert validate_document_token(token, "cv_abc.pdf")
        assert not validate_document_token(token, "other.pdf")

    def test_token_rejects_tampering(self):
        token = create_document_token(["cv_abc.pdf"])
        encoded, signature = token.split(".", 1)
        assert not validate_document_token(f"{encoded}.{'0' * len(signature)}", "cv_abc.pdf")


class TestOutboundUrls:
    def test_requires_https(self):
        with pytest.raises(ValueError):
            validate_public_https_url("http://example.com")

    def test_rejects_private_ip(self):
        with pytest.raises(ValueError):
            validate_public_https_url("https://127.0.0.1")
