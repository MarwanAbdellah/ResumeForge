"""Interfaces shared by deterministic discovery workers."""

from typing import Protocol

from models.pipeline import ATSKeywordModel, EvidenceChunk


class DiscoveryWorker(Protocol):
    name: str

    def supports(self, url: str) -> bool:
        """Return whether this worker owns the URL."""

    def fetch(self, url: str, keywords: ATSKeywordModel) -> list[EvidenceChunk]:
        """Fetch and normalize verified evidence for one URL."""
