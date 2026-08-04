"""GitHub discovery worker backed by the existing guarded fetcher.

Emits one ``EvidenceChunk`` per relevant repository so repo names, README
excerpts, and descriptions can be scored by the coordinator instead of being
buried inside a single profile-level chunk. READMEs are fetched for the
keyword-relevant repositories (not only the most-starred few), and any URLs
inside those READMEs (e.g. a Tableau dashboard) are captured as ``related_links``.
"""

from urllib.parse import urlparse

from models.pipeline import ATSKeywordModel, EvidenceChunk
from tools.link_fetcher import (
    _fetch_github_repo_readme,
    extract_urls_from_text,
    fetch_portfolio_links,
    infer_technologies,
)

MAX_RELEVANT_READMES = 8
README_LINK_SCAN_CHARS = 4000


class GitHubWorker:
    name = "github"

    def supports(self, url: str) -> bool:
        host = (urlparse(url if "://" in url else f"https://{url}").hostname or "").lower()
        return host in {"github.com", "www.github.com"}

    def fetch(self, url: str, keywords: ATSKeywordModel) -> list[EvidenceChunk]:
        items = fetch_portfolio_links([url])
        chunks: list[EvidenceChunk] = []
        for item in items:
            self._augment_readmes(item, keywords)
            chunks.extend(self._chunks(item, url))
        return chunks

    @staticmethod
    def _keyword_terms(keywords: ATSKeywordModel) -> set[str]:
        terms = set()
        for group in (
            keywords.required_keywords,
            keywords.preferred_keywords,
            keywords.technical_terms,
            keywords.role_terms,
        ):
            for term in group:
                if term and term.strip():
                    terms.add(term.strip().lower())
        return terms

    @staticmethod
    def _repo_relevance(repo: dict, terms: set[str]) -> int:
        haystack = " ".join(
            [
                repo.get("name", ""),
                repo.get("description", "") or "",
                repo.get("language", "") or "",
                *(repo.get("topics", []) or []),
            ]
        ).lower()
        return sum(1 for term in terms if term in haystack)

    def _augment_readmes(self, item: dict, keywords: ATSKeywordModel) -> None:
        """Fetch READMEs for keyword-relevant repos and scan them for links."""
        terms = self._keyword_terms(keywords)
        repos = item.get("repos") or []

        ranked = sorted(
            repos,
            key=lambda repo: (self._repo_relevance(repo, terms), repo.get("stars", 0)),
            reverse=True,
        )
        for repo in ranked[:MAX_RELEVANT_READMES]:
            if not repo.get("readme_excerpt") and repo.get("full_name"):
                readme = _fetch_github_repo_readme(
                    repo["full_name"], max_chars=README_LINK_SCAN_CHARS
                )
                if readme:
                    repo["readme_excerpt"] = readme

        for repo in repos:
            repo["related_links"] = extract_urls_from_text(
                repo.get("readme_excerpt") or ""
            )

        if not repos:
            readme = item.get("readme_excerpt") or ""
            item["related_links"] = extract_urls_from_text(readme)

    def _chunks(self, item: dict, fallback_url: str) -> list[EvidenceChunk]:
        repos = item.get("repos") or []
        chunks = [self._repo_chunk(repo) for repo in repos if repo.get("name")]
        profile_chunk = self._profile_chunk(item, fallback_url, len(repos))
        if profile_chunk is not None:
            chunks.append(profile_chunk)
        if not chunks:
            chunks.append(self._chunk(item, fallback_url))
        return chunks

    def _repo_chunk(self, repo: dict) -> EvidenceChunk:
        technologies = []
        if repo.get("language"):
            technologies.append(repo["language"])
        technologies.extend(repo.get("topics") or [])
        description = repo.get("description") or ""
        readme = repo.get("readme_excerpt") or ""
        combined = " ".join(filter(None, [repo.get("name", ""), description, readme]))
        technologies.extend(infer_technologies(combined))
        technologies = list(dict.fromkeys(t for t in technologies if t))

        summary = " ".join(filter(None, [description, readme]))[:1200]
        return EvidenceChunk(
            source=self.name,
            platform="github",
            url=repo.get("url") or repo.get("html_url") or "",
            title=repo.get("name") or "",
            summary=summary,
            technologies=technologies,
            verified=True,
            raw=repo,
        )

    def _profile_chunk(self, item: dict, fallback_url: str, repo_count: int) -> EvidenceChunk | None:
        languages = item.get("all_languages") or []
        topics = item.get("all_topics") or []
        title = item.get("title") or item.get("name") or ""
        if not title and not languages and not topics:
            return None
        summary = item.get("description") or item.get("bio") or ""
        if repo_count:
            summary = f"{summary} ({repo_count} public repositories)".strip()
        return EvidenceChunk(
            source=self.name,
            platform=item.get("platform", "github"),
            url=item.get("url") or fallback_url,
            title=title,
            summary=summary,
            technologies=[*languages, *topics],
            verified=True,
            raw=item,
        )

    def _chunk(self, item: dict, fallback_url: str) -> EvidenceChunk:
        technologies = list(item.get("all_languages", [])) + list(item.get("all_topics", []))
        title = item.get("title") or item.get("name") or item.get("project_name") or ""
        summary = item.get("description", "") or item.get("bio", "") or ""
        return EvidenceChunk(
            source=self.name,
            platform=item.get("platform", "github"),
            url=item.get("url") or item.get("source_url") or fallback_url,
            title=title,
            summary=summary,
            technologies=technologies,
            verified=True,
            raw=item,
        )
