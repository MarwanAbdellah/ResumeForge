"""API-facing structured pipeline operations."""

import json

from models.schemas import Candidate
from tools.extractors import extract_text

from .ai_service import AIService
from .generation_service import GenerationService


def flatten_candidate(candidate: Candidate | dict) -> str:
    model = candidate if isinstance(candidate, Candidate) else Candidate.model_validate(candidate)
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2)


class PipelineService:
    def __init__(self, ai: AIService | None = None):
        self.ai = ai or AIService()
        self.generation = GenerationService(self.ai)

    def extract(self, content: bytes, filename: str) -> str:
        return extract_text(content, filename)

    def structure(self, source_text: str, notes: str = "") -> Candidate:
        source = source_text if not notes.strip() else f"{source_text}\n\nCandidate notes:\n{notes.strip()}"
        return self.ai.run("structure_resume", {"source_text": source})

    def analyze(self, job_description: str):
        return self.generation.analyze_job(job_description)

    def audit(self, candidate_data: dict, job_description: str):
        return self.generation.ats_check(Candidate.model_validate(candidate_data), job_description)
