"""Generic portfolio/web discovery worker.

Turns search-backed results (e.g. Kaggle notebooks found via Serper) into
individual evidence chunks alongside the profile-level chunk.
"""

from urllib.parse import urlparse

from models.pipeline import ATSKeywordModel, EvidenceChunk
from tools.link_fetcher import fetch_portfolio_links


class PortfolioWorker:
    name = "portfolio"

    def supports(self, url: str) -> bool:
        host = (urlparse(url if "://" in url else f"https://{url}").hostname or "").lower()
        return not host.endswith("github.com")

    def fetch(self, url: str, keywords: ATSKeywordModel) -> list[EvidenceChunk]:
        del keywords
        items = fetch_portfolio_links([url])
        chunks: list[EvidenceChunk] = []
        for item in items:
            for result in item.get("search_results") or []:
                if result.get("title"):
                    chunks.append(self._search_chunk(result, url))
            chunks.append(self._chunk(item, url))
        return chunks

    def _search_chunk(self, result: dict, fallback_url: str) -> EvidenceChunk:
        return EvidenceChunk(
            source=self.name,
            platform=result.get("platform", "kaggle"),
            url=result.get("url") or fallback_url,
            title=result.get("title", ""),
            summary=result.get("summary", ""),
            technologies=result.get("technologies", []),
            verified=True,
            raw=result,
        )

    def _chunk(self, item: dict, fallback_url: str) -> EvidenceChunk:
        return EvidenceChunk(
            source=self.name,
            platform=item.get("platform", "website"),
            url=item.get("url") or fallback_url,
            title=item.get("title", ""),
            summary=item.get("description", ""),
            technologies=item.get("technologies", []),
            verified=bool(item.get("verified", True)),
            raw=item,
        )
