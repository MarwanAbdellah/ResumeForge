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
