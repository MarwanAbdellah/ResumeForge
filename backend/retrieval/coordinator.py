"""Concurrent discovery coordination and typed evidence aggregation."""

import asyncio
import re
from typing import Iterable

from models.pipeline import (
    ATSKeywordModel,
    CandidateEvidenceModel,
    EvidenceChunk,
    SourceStatus,
)

from .base import DiscoveryWorker
from .workers import GitHubWorker, PortfolioWorker


class DiscoveryCoordinator:
    """Routes links to registered workers and aggregates their evidence.

    New workers are added through the constructor registry; the pipeline graph
    does not need to change.
    """

    def __init__(self, workers: Iterable[DiscoveryWorker] | None = None):
        self.workers = list(workers or (GitHubWorker(), PortfolioWorker()))

    def _worker_for(self, url: str) -> DiscoveryWorker | None:
        return next((worker for worker in self.workers if worker.supports(url)), None)

    async def gather(
        self, links: list[str], keywords: ATSKeywordModel
    ) -> CandidateEvidenceModel:
        if not links:
            return CandidateEvidenceModel()

        async def run_one(url: str):
            worker = self._worker_for(url)
            if worker is None:
                return [], SourceStatus(worker="unknown", url=url, status="skipped", detail="No registered worker")
            try:
                chunks = await asyncio.to_thread(worker.fetch, url, keywords)
                for chunk in chunks:
                    chunk.relevance_score = self._score(chunk, keywords)
                detail = self._source_detail(worker.name, url, chunks)
                return chunks, SourceStatus(worker=worker.name, url=url, status="ok", detail=detail)
            except Exception as exc:
                return [], SourceStatus(worker=worker.name, url=url, status="error", detail=type(exc).__name__)

        results = await asyncio.gather(*(run_one(url) for url in links))
        chunks = [chunk for found, _ in results for chunk in found]
        sources = [source for _, source in results]
        warnings = [
            f"{source.worker} failed for {source.url}: {source.detail}"
            for source in sources
            if source.status == "error"
        ]
        chunks.sort(key=lambda chunk: chunk.relevance_score, reverse=True)
        return CandidateEvidenceModel(chunks=chunks, sources=sources, warnings=warnings)

    @staticmethod
    def _source_detail(worker: str, url: str, chunks: list[EvidenceChunk]) -> str:
        """Human-readable per-source summary surfaced to the user."""
        normalized_url = (url or "").rstrip("/").lower()
        platforms = {chunk.platform for chunk in chunks if chunk.platform}
        sub_items = [
            chunk
            for chunk in chunks
            if chunk.title and chunk.url and chunk.url.rstrip("/").lower() != normalized_url
        ]

        if worker == "github":
            if sub_items:
                return f"fetched {len(sub_items)} repositories/projects"
            return "profile fetched" if chunks else "no data"
        if "linkedin" in platforms:
            return "link preserved, profile content not fetched (LinkedIn blocks scrapers)"
        if sub_items:
            return f"metadata plus {len(sub_items)} notebooks/datasets via search"
        return "metadata only"

    @staticmethod
    def _score(chunk: EvidenceChunk, keywords: ATSKeywordModel) -> float:
        terms = {
            term.lower()
            for term in (
                keywords.required_keywords
                + keywords.preferred_keywords
                + keywords.technical_terms
                + keywords.role_terms
            )
            if term.strip()
        }
        haystack_parts = [chunk.title, chunk.summary, *chunk.technologies]
        if isinstance(chunk.raw, dict):
            for value in chunk.raw.values():
                if isinstance(value, str) and value:
                    haystack_parts.append(value)
                elif isinstance(value, list):
                    haystack_parts.extend(str(v) for v in value if isinstance(v, str))
        haystack = " ".join(haystack_parts).lower()
        return float(sum(1 for term in terms if re.search(rf"\b{re.escape(term)}\b", haystack)))
