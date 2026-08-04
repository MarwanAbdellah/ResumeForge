"""Pipeline-level domain models.

These models sit above the base candidate's extracted-fact models and describe
per-run pipeline artifacts: ATS keyword discovery, aggregated candidate
evidence, the optimized resume, cover-letter review, and the immutable context
shared by the generation agents.
"""

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .schemas import (
    Candidate,
    Certification,
    CoverLetter,
    Education,
    Experience,
    JobAnalysis,
    Language,
    Project,
    Skill,
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ATSKeywordModel(_Strict):
    """ATS-critical keywords extracted from a job description."""

    required_keywords: list[str] = Field(default_factory=list)
    preferred_keywords: list[str] = Field(default_factory=list)
    technical_terms: list[str] = Field(default_factory=list)
    role_terms: list[str] = Field(default_factory=list)


class EvidenceChunk(_Strict):
    """A single piece of verified public evidence produced by a discovery worker."""

    source: str
    platform: str = ""
    url: str | None = None
    title: str = ""
    summary: str = ""
    technologies: list[str] = Field(default_factory=list)
    relevance_score: float = 0.0
    verified: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class SourceStatus(_Strict):
    worker: str
    url: str | None = None
    status: Literal["ok", "error", "skipped"] = "ok"
    detail: str = ""


class ExternalProjectModel(_Strict):
    """A verified project projected from external evidence (GitHub/Kaggle)."""

    name: str = ""
    url: str = ""
    description: str = ""
    bullets: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    demo_url: str | None = None
    relevance_score: float = 0.0
    source: str = ""


class CandidateEvidenceModel(_Strict):
    """Aggregated evidence from all discovery workers."""

    chunks: list[EvidenceChunk] = Field(default_factory=list)
    sources: list[SourceStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResumeModel(_Strict):
    """An optimized, ATS-ready resume targeted at a specific role.

    Distinct from CandidateModel: a candidate holds extracted facts, a resume
    holds a tailored presentation of those facts for one job description.
    """

    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    headline: str = ""
    summary: str = ""
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    ats_keywords_used: list[str] = Field(default_factory=list)


class CoverLetterReviewModel(_Strict):
    score: int = Field(default=0, ge=0, le=100)
    verdict: str = ""
    strengths: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class GenerationContextModel(BaseModel):
    """Immutable, validated context handed to every generation agent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate: Candidate
    job_analysis: JobAnalysis
    ats_keywords: ATSKeywordModel
    evidence: CandidateEvidenceModel
    evidence_projects: list[ExternalProjectModel] = Field(default_factory=list)
    job_description: str = Field(min_length=1)
    notes: str = ""

    def candidate_json(self) -> str:
        return self.candidate.model_dump_json()

    def job_analysis_json(self) -> str:
        return self.job_analysis.model_dump_json()

    def keywords_json(self) -> str:
        return self.ats_keywords.model_dump_json()

    def evidence_json(self) -> str:
        return self.evidence.model_dump_json()

    def evidence_projects_json(self) -> str:
        return json.dumps(
            [project.model_dump(mode="json") for project in self.evidence_projects],
            ensure_ascii=False,
            indent=2,
        )