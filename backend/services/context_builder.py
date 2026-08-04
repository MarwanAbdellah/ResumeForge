"""Deterministic composition of validated generation inputs."""

from models.pipeline import (
    ATSKeywordModel,
    CandidateEvidenceModel,
    GenerationContextModel,
)
from models.schemas import Candidate, JobAnalysis

from observability.events import emit_event, stage_span
from .evidence_projects import build_external_projects


class GenerationContextBuilder:
    """Builds a shared context without mutating any upstream model."""

    def build(
        self,
        candidate: Candidate,
        job_analysis: JobAnalysis,
        ats_keywords: ATSKeywordModel,
        evidence: CandidateEvidenceModel,
        job_description: str,
        notes: str = "",
    ) -> GenerationContextModel:
        with stage_span("generation_context", component="GenerationContextBuilder"):
            context = GenerationContextModel.model_validate(
                {
                    "candidate": Candidate.model_validate(candidate.model_dump()),
                    "job_analysis": JobAnalysis.model_validate(job_analysis.model_dump()),
                    "ats_keywords": ATSKeywordModel.model_validate(ats_keywords.model_dump()),
                    "evidence": CandidateEvidenceModel.model_validate(evidence.model_dump()),
                    "evidence_projects": [
                        project.model_dump()
                        for project in build_external_projects(evidence, ats_keywords)
                    ],
                    "job_description": job_description,
                    "notes": notes,
                }
            )
            emit_event("generation_context", "validated", validation_status="passed")
            return context
