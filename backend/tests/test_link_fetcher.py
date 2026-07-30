"""
Unit tests for the Live Profile Enrichment Engine and helper functions in crew.py.
"""

import pytest
from unittest.mock import patch, MagicMock
from tools.link_fetcher import (
    _extract_github_username,
    _extract_github_repo_path,
    _is_github_profile,
    _detect_platform,
    fetch_portfolio_links,
)
from crew import _extract_html, _normalize_phone_numbers


class TestGitHubURLParsing:
    def test_extract_username_from_profile_url(self):
        assert _extract_github_username("https://github.com/MarwanAbdellah") == "MarwanAbdellah"
        assert _extract_github_username("http://github.com/john_doe/") == "john_doe"

    def test_extract_username_from_repo_url(self):
        assert _extract_github_username("https://github.com/MarwanAbdellah/tips_hindawi") == "MarwanAbdellah"

    def test_is_github_profile(self):
        assert _is_github_profile("https://github.com/MarwanAbdellah") is True
        assert _is_github_profile("https://github.com/MarwanAbdellah/repo_name") is False

    def test_extract_repo_path(self):
        assert _extract_github_repo_path("https://github.com/MarwanAbdellah/tips_hindawi") == "MarwanAbdellah/tips_hindawi"
        assert _extract_github_repo_path("https://github.com/MarwanAbdellah") is None


class TestPlatformDetection:
    def test_detects_known_platforms(self):
        assert _detect_platform("https://github.com/user") == "github"
        assert _detect_platform("https://kaggle.com/user") == "kaggle"
        assert _detect_platform("https://huggingface.co/models") == "huggingface"
        assert _detect_platform("https://linkedin.com/in/user") == "linkedin"
        assert _detect_platform("https://myportfolio.dev") == "website"


class TestHTMLExtractionAndPhoneNormalization:
    def test_extract_html_strips_markdown_code_fences(self):
        raw = "```html\n<!DOCTYPE html><html><body><h1>Title</h1></body></html>\n```"
        extracted = _extract_html(raw)
        assert extracted.startswith("<!DOCTYPE html>")
        assert extracted.endswith("</html>")
        assert "```" not in extracted

    def test_extract_html_handles_no_fences(self):
        raw = "<!DOCTYPE html><html><body><h1>Clean</h1></body></html>"
        assert _extract_html(raw) == raw

    def test_phone_normalization_preserves_egyptian_digits(self):
        # Egyptian number: +20 01029388461 -> 12 digits total starting with 20
        html = "<div>(+20) 01029388461</div>"
        normalized = _normalize_phone_numbers(html)
        assert "(+20)" in normalized
        # Ensure digits 01029388461 are present
        assert "010" in normalized

    def test_phone_normalization_handles_us_numbers(self):
        html = "<div>+15551234567</div>"
        normalized = _normalize_phone_numbers(html)
        assert "(+1) 555-123-4567" in normalized


class TestFetchPortfolioLinksMocked:
    @patch("tools.link_fetcher._fetch_json")
    def test_fetch_github_profile(self, mock_fetch_json):
        # Mock user info call
        mock_fetch_json.side_effect = [
            # User info
            {"name": "Marwan", "bio": "AI Engineer", "public_repos": 5},
            # Repos list
            [
                {
                    "name": "FakeNewsDetection",
                    "full_name": "Marwan/FakeNewsDetection",
                    "description": "Multi-agent news classifier",
                    "html_url": "https://github.com/Marwan/FakeNewsDetection",
                    "language": "Python",
                    "stargazers_count": 12,
                    "topics": ["crewai", "nlp"],
                    "fork": False,
                }
            ],
            # README call for top repo
            {"content": "IyMgRmFrZSBOZXdzIERldGVjdGlvbgoKVGhpcyBpcyBhIDQtYWdlbnQgQ3Jld0FJLi4u"},  # "## Fake News Detection\n\nThis is a 4-agent CrewAI..." in b64
        ]

        results = fetch_portfolio_links(["https://github.com/Marwan"])
        assert len(results) == 1
        entry = results[0]
        assert entry["platform"] == "github"
        assert entry["title"] == "Marwan"
        assert len(entry["repos"]) == 1
        assert entry["repos"][0]["name"] == "FakeNewsDetection"
        assert entry["repos"][0]["stars"] == 12
