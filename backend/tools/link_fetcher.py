"""
Live Profile Enrichment Engine.
Fetches and structures data from GitHub API, Kaggle, HuggingFace, and portfolio sites.
"""

import re
import json
import logging
import urllib.request
import urllib.error
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

import os

# GitHub API base
GITHUB_API = "https://api.github.com"
SERPER_API_URL = "https://google.serper.dev/search"

# Max repos to extract per profile
MAX_REPOS = 30
# Max README chars to extract per repo
MAX_README_CHARS = 800


def search_serper_web(query: str, max_results: int = 5) -> list[dict]:
    """
    Query Google via Serper Dev API to discover unlinked candidate repositories,
    Kaggle notebooks, medium posts, or portfolio entries.
    Requires SERPER_API_KEY environment variable.
    """
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        logger.info("[Serper Dev] SERPER_API_KEY not found — skipping web search.")
        return []

    logger.info(f"[Serper Dev] 🌐 Searching web for: '{query}'")
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = json.dumps({"q": query, "num": max_results}).encode("utf-8")

    req = urllib.request.Request(SERPER_API_URL, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            organic = data.get("organic", [])
            results = []
            for item in organic[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })
            logger.info(f"[Serper Dev] Found {len(results)} search results for '{query}'")
            return results
    except Exception as e:
        logger.warning(f"[Serper Dev] Search failed for '{query}': {e}")
        return []


# ══════════════════════════════════════════════════════════
#  HTTP HELPERS
# ══════════════════════════════════════════════════════════

def _fetch_html(url: str, timeout: int = 8) -> str:
    """Fetch raw HTML from a URL with a browser-like User-Agent."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ResumeForge/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return data.decode("latin-1")
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return ""


def _fetch_json(url: str, timeout: int = 8) -> dict | list | None:
    """Fetch JSON from a URL (used for GitHub API)."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ResumeForge/1.0",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning(f"Failed to fetch JSON from {url}: {e}")
        return None


# ══════════════════════════════════════════════════════════
#  META TAG EXTRACTION (Portfolio / Kaggle / HuggingFace)
# ══════════════════════════════════════════════════════════

class _MetaParser(HTMLParser):
    """Extract og:title and og:description from HTML head."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        self._in_title_tag = False
        self._capture = ""

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == "meta":
            prop = attr_dict.get("property", "")
            name = attr_dict.get("name", "")
            if prop == "og:title" or name == "og:title":
                self.title = attr_dict.get("content", "")
            elif prop == "og:description" or name == "description":
                if not self.description:
                    self.description = attr_dict.get("content", "")
        if tag == "title":
            self._in_title_tag = True
            self._capture = ""

    def handle_data(self, data):
        if self._in_title_tag and not self.title:
            self._capture += data

    def handle_endtag(self, tag):
        if tag == "title" and self._in_title_tag:
            if not self.title:
                self.title = self._capture.strip()
            self._in_title_tag = False


def _extract_meta(html: str) -> dict:
    """Extract title and description from meta tags."""
    parser = _MetaParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    return {"title": parser.title, "description": parser.description}


# ══════════════════════════════════════════════════════════
#  GITHUB API ENRICHMENT (primary enrichment source)
# ══════════════════════════════════════════════════════════

def _extract_github_username(url: str) -> str | None:
    """Extract GitHub username from a GitHub profile or repo URL."""
    url = url.rstrip("/")
    match = re.match(r"https?://github\.com/([^/?#]+)(?:/.*)?$", url, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_github_repo_path(url: str) -> str | None:
    """Extract 'owner/repo' from a GitHub repo URL, or None if it's a profile."""
    url = url.rstrip("/")
    match = re.match(r"https?://github\.com/([^/?#]+)/([^/?#]+)$", url, re.IGNORECASE)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return None


def _fetch_github_profile_repos(username: str) -> list[dict]:
    """
    Fetch up to MAX_REPOS repos for a GitHub user via the GitHub API.
    Returns a list of structured repo dicts sorted by stars descending.
    """
    data = _fetch_json(f"{GITHUB_API}/users/{username}/repos?per_page=100&type=owner&sort=pushed")
    if not isinstance(data, list):
        return []

    repos = []
    for repo in data:
        if repo.get("fork"):
            continue  # Skip forked repos
        topics = repo.get("topics", []) or []
        repos.append({
            "name": repo.get("name", ""),
            "full_name": repo.get("full_name", ""),
            "description": (repo.get("description") or "")[:300],
            "url": repo.get("html_url", ""),
            "language": repo.get("language") or "",
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "topics": topics[:8],
        })

    # Sort by stars descending, then return top N
    repos.sort(key=lambda r: r["stars"], reverse=True)
    return repos[:MAX_REPOS]


def _fetch_github_repo_readme(full_name: str) -> str:
    """Fetch the first MAX_README_CHARS chars of a repo's README via GitHub API."""
    data = _fetch_json(f"{GITHUB_API}/repos/{full_name}/readme")
    if not isinstance(data, dict):
        return ""
    # README content is base64 encoded
    import base64
    content_b64 = data.get("content", "")
    try:
        content = base64.b64decode(content_b64.replace("\n", "")).decode("utf-8", errors="replace")
        # Strip markdown headers and code blocks for cleaner text
        content = re.sub(r"#{1,6}\s+", "", content)
        content = re.sub(r"```[\s\S]*?```", "", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content[:MAX_README_CHARS].strip()
    except Exception:
        return ""


def _fetch_github_user_info(username: str) -> dict:
    """Fetch basic GitHub user profile info."""
    data = _fetch_json(f"{GITHUB_API}/users/{username}")
    if not isinstance(data, dict):
        return {}
    return {
        "name": data.get("name") or username,
        "bio": (data.get("bio") or "")[:300],
        "company": data.get("company") or "",
        "location": data.get("location") or "",
        "public_repos": data.get("public_repos", 0),
        "followers": data.get("followers", 0),
        "blog": data.get("blog") or "",
    }


def _enrich_github_profile(url: str) -> dict:
    """
    Full GitHub profile enrichment using the public GitHub API.
    Returns a rich dict with user info, top repos, and per-repo tech stack.
    """
    username = _extract_github_username(url)
    if not username:
        return {"url": url, "platform": "github", "title": "", "description": "", "repos": []}

    logger.info(f"[Enrichment] Fetching GitHub profile for: {username}")

    user_info = _fetch_github_user_info(username)
    repos = _fetch_github_profile_repos(username)

    # Aggregate all unique languages and topics across repos
    all_languages = list({r["language"] for r in repos if r["language"]})
    all_topics = list({t for r in repos for t in r.get("topics", [])})

    # Optionally fetch README for top 3 repos (most starred)
    for repo in repos[:3]:
        if repo.get("full_name"):
            readme = _fetch_github_repo_readme(repo["full_name"])
            if readme:
                repo["readme_excerpt"] = readme

    return {
        "url": url,
        "platform": "github",
        "title": user_info.get("name", username),
        "description": user_info.get("bio", ""),
        "github_username": username,
        "github_user_info": user_info,
        "repos": repos,
        "all_languages": all_languages,
        "all_topics": all_topics,
    }


def _enrich_github_repo(url: str) -> dict:
    """Fetch a single GitHub repository's details."""
    repo_path = _extract_github_repo_path(url)
    if not repo_path:
        return {"url": url, "platform": "github", "title": "", "description": "", "repos": []}

    logger.info(f"[Enrichment] Fetching GitHub repo: {repo_path}")
    data = _fetch_json(f"{GITHUB_API}/repos/{repo_path}")
    if not isinstance(data, dict):
        return {"url": url, "platform": "github", "title": repo_path.split("/")[-1], "description": "", "repos": []}

    readme = _fetch_github_repo_readme(repo_path)
    topics = data.get("topics", []) or []

    return {
        "url": url,
        "platform": "github",
        "title": data.get("name", ""),
        "description": (data.get("description") or "")[:300],
        "language": data.get("language") or "",
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "topics": topics[:8],
        "readme_excerpt": readme,
        "repos": [],
    }


# ══════════════════════════════════════════════════════════
#  PLATFORM DETECTION & GENERIC ENRICHMENT
# ══════════════════════════════════════════════════════════

def _detect_platform(url: str) -> str:
    """Detect the platform from a URL."""
    url_lower = url.lower()
    if "github.com" in url_lower:
        return "github"
    if "huggingface.co" in url_lower:
        return "huggingface"
    if "kaggle.com" in url_lower:
        return "kaggle"
    if "linkedin.com" in url_lower:
        return "linkedin"
    if "dev.to" in url_lower:
        return "devto"
    if "gitlab.com" in url_lower:
        return "gitlab"
    return "website"


def _is_github_profile(url: str) -> bool:
    """Check if URL is a GitHub user profile (not a specific repo)."""
    path = re.sub(r"https?://github\.com/", "", url, flags=re.IGNORECASE).strip("/")
    parts = [p for p in path.split("/") if p]
    # Profile URL: github.com/username (exactly 1 path segment)
    return len(parts) == 1


def _extract_title_from_url(url: str) -> str:
    """Extract a readable title from the URL path."""
    path = url.rstrip("/").split("/")[-1]
    return path.replace("-", " ").replace("_", " ").title() if path else url


def _enrich_generic(url: str, platform: str) -> dict:
    """Generic enrichment for Kaggle, HuggingFace, portfolio sites."""
    # LinkedIn blocks scrapers with HTTP 999 — return clean link object without scraping attempt
    if platform == "linkedin":
        logger.info(f"[Enrichment] Preserving LinkedIn profile link: {url}")
        return {
            "url": url,
            "platform": "linkedin",
            "title": _extract_title_from_url(url),
            "description": "LinkedIn Profile",
            "repos": [],
        }

    logger.info(f"[Enrichment] Fetching {platform}: {url}")
    html = _fetch_html(url)
    if not html:
        return {
            "url": url,
            "platform": platform,
            "title": _extract_title_from_url(url),
            "description": "",
            "repos": [],
        }
    meta = _extract_meta(html)
    return {
        "url": url,
        "platform": platform,
        "title": meta["title"] or _extract_title_from_url(url),
        "description": meta["description"][:400] if meta["description"] else "",
        "repos": [],
    }


# ══════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════

def fetch_portfolio_links(urls: list[str]) -> list[dict]:
    """
    Fetch and enrich a list of portfolio/profile URLs.
    Uses GitHub API for GitHub links (much richer data than HTML scraping).
    Falls back to HTML meta-tag scraping for other platforms.

    Returns a list of enriched profile/project dicts.
    """
    results = []

    for url in urls:
        url = url.strip()
        if not url:
            continue

        # Normalize URL scheme
        if not url.startswith("http"):
            url = "https://" + url

        platform = _detect_platform(url)

        try:
            if platform == "github":
                if _is_github_profile(url):
                    entry = _enrich_github_profile(url)
                else:
                    entry = _enrich_github_repo(url)
            else:
                entry = _enrich_generic(url, platform)
        except Exception as e:
            logger.warning(f"[Enrichment] Failed to enrich {url}: {e}")
            entry = {
                "url": url,
                "platform": platform,
                "title": _extract_title_from_url(url),
                "description": "",
                "repos": [],
            }

        results.append(entry)
        logger.info(f"[Enrichment] Enriched {url} ({platform}): {entry.get('title', '')}")

    return results
