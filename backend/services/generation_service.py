"""DAG-backed generation workflow using validated models only."""

import asyncio
import uuid
from typing import Any

from models.pipeline import (
    ATSKeywordModel,
    CandidateEvidenceModel,
    CoverLetterReviewModel,
    ResumeModel,
)
from models.schemas import ATSReport, Candidate, CoverLetter, JobAnalysis
from config.prompts import HUMANIZER_GUIDANCE
from observability.events import emit_event, stage_span
from observability.metrics import metrics
from renderers import render_cover_letter, render_resume
from retrieval import DiscoveryCoordinator
from security import create_document_token

from .ai_service import AIService
from .ats_postprocess import postprocess_ats_report
from .context_builder import GenerationContextBuilder
from .dag import Node, PipelineState, execute_dag
from .document_service import DocumentService
from .evidence_projects import ensure_evidence_projects
from .tailoring import (
    TailoringPlan,
    build_tailoring_plan,
    summarize_issues,
    token_overlap,
    validate_generated_resume,
)

ECHO_OVERLAP_THRESHOLD = 0.85


def _candidate_text(candidate: Candidate) -> str:
    """The original candidate prose used for echo detection."""
    parts = [candidate.summary or ""]
    for exp in candidate.experience:
        parts.append(exp.title or "")
        parts.extend(exp.bullets or [])
    for project in candidate.projects:
        parts.append(project.name or "")
        parts.append(project.description or "")
        parts.extend(project.bullets or [])
    return "\n".join(parts)


def _generated_text(resume: ResumeModel) -> str:
    parts = [resume.summary or ""]
    for exp in resume.experience:
        parts.append(exp.title or "")
        parts.extend(exp.bullets or [])
    for project in resume.projects:
        parts.append(project.name or "")
        parts.append(project.description or "")
        parts.extend(project.bullets or [])
    return "\n".join(parts)


def _echo_guard_diff(resume: ResumeModel, candidate: Candidate) -> str:
    overlap = token_overlap(_generated_text(resume), _candidate_text(candidate))
    if overlap < ECHO_OVERLAP_THRESHOLD:
        return ""
    return (
        f"The generated resume shares {round(overlap * 100)}% of its tokens with the input "
        "candidate. This is an unacceptable echo. Rewrite the summary so it is clearly aimed at "
        "the target role, reorder skills by JD relevance, and produce at least one new tailored "
        "bullet per experience and project. Preserve all facts, dates, and URLs exactly."
    )


def _resume_model(value: ResumeModel | Candidate) -> ResumeModel:
    if isinstance(value, ResumeModel):
        return value
    data = value.model_dump(mode="json")
    return ResumeModel.model_validate(
        {key: data[key] for key in ResumeModel.model_fields if key in data}
    )


class GenerationService:
    def __init__(
        self,
        ai: AIService | None = None,
        documents: DocumentService | None = None,
        discovery: DiscoveryCoordinator | None = None,
        context_builder: GenerationContextBuilder | None = None,
    ):
        self.ai = ai or AIService()
        self.documents = documents or DocumentService()
        self.discovery = discovery or DiscoveryCoordinator()
        self.context_builder = context_builder or GenerationContextBuilder()

    def analyze_job(self, job_description: str) -> JobAnalysis:
        return self.ai.run("analyze_job", {"job_description": job_description})

    def extract_keywords(self, job_description: str) -> ATSKeywordModel:
        return self.ai.run("extract_ats_keywords", {"job_description": job_description})

    def structure(self, extracted_text: str) -> Candidate:
        return self.ai.run("structure_resume", {"source_text": extracted_text})

    def ats_check(
        self,
        candidate: Candidate,
        job_description: str,
        analysis: JobAnalysis | None = None,
        evidence: CandidateEvidenceModel | None = None,
    ) -> ATSReport:
        analysis = analysis or self.analyze_job(job_description)
        evidence_json = (
            evidence.model_dump_json()
            if evidence is not None
            else CandidateEvidenceModel().model_dump_json()
        )
        report = self.ai.run(
            "review_ats",
            {
                "resume_json": candidate.model_dump_json(),
                "job_analysis_json": analysis.model_dump_json(),
                "evidence_json": evidence_json,
            },
        )
        return postprocess_ats_report(report, candidate, analysis, evidence)

    async def generate_async(
        self,
        candidate_data: dict[str, Any],
        job_description: str,
        output_type: str,
        notes: str = "",
        portfolio_links: list[str] | None = None,
    ) -> dict[str, Any]:
        run_id = uuid.uuid4().hex[:8]
        links = portfolio_links or []

        async def validate_candidate(state: PipelineState):
            return Candidate.model_validate(state.require("candidate_data"))

        async def analyze_job(state: PipelineState):
            return await asyncio.to_thread(self.analyze_job, state.require("job_description"))

        async def extract_keywords(state: PipelineState):
            try:
                return await asyncio.to_thread(self.extract_keywords, state.require("job_description"))
            except AssertionError:
                # Compatibility for injected legacy fakes during migration.
                return ATSKeywordModel()

        async def discover(state: PipelineState):
            return await self.discovery.gather(
                state.require("portfolio_links"), state.require("extract_ats_keywords")
            )

        async def build_context(state: PipelineState):
            return self.context_builder.build(
                state.require("validate_candidate"),
                state.require("analyze_job"),
                state.require("extract_ats_keywords"),
                state.require("discovery"),
                state.require("job_description"),
                state.get("notes", ""),
            )

        def _resume_inputs(
            context,
            plan: TailoringPlan,
            echo_guard_diff: str = "",
            validation_issues: str = "",
        ) -> dict[str, Any]:
            return {
                "candidate_json": context.candidate_json(),
                "job_analysis_json": context.job_analysis_json(),
                "keywords_json": context.keywords_json(),
                "evidence_json": context.evidence_json(),
                "verified_projects": context.evidence_projects_json(),
                "tailoring_plan": plan.to_json(),
                "notes": context.notes,
                "echo_guard_diff": echo_guard_diff,
                "validation_issues": validation_issues,
                "humanizer_guidance": HUMANIZER_GUIDANCE,
            }

        def _run_resume_once(
            context, plan: TailoringPlan, echo_guard_diff: str = "", validation_issues: str = ""
        ) -> ResumeModel:
            inputs = _resume_inputs(context, plan, echo_guard_diff, validation_issues)
            try:
                result = self.ai.run("generate_resume", inputs)
            except AssertionError:
                result = self.ai.run(
                    "optimize_resume",
                    {
                        "candidate_json": context.candidate_json(),
                        "job_analysis": context.job_analysis_json(),
                    },
                )
            return _resume_model(result)

        async def generate_resume(state: PipelineState):
            context = state.require("build_context")
            plan = build_tailoring_plan(
                context.candidate, context.job_analysis, context.ats_keywords, context.evidence
            )
            resume = await asyncio.to_thread(_run_resume_once, context, plan)
            resume = ensure_evidence_projects(
                resume, context.evidence_projects, top_n=2
            )

            echo_diff = _echo_guard_diff(resume, context.candidate)
            issues = validate_generated_resume(
                resume, context.candidate, plan, context.evidence
            )
            critical = (
                issues["summary_echo"] + issues["invented_skills"] + issues["fact_integrity"]
            )
            if echo_diff or critical:
                repair_note = "\n".join(filter(None, [echo_diff, summarize_issues(issues)]))
                emit_event(
                    "generate_resume",
                    "repair_retry",
                    echo_overlap=round(token_overlap(_generated_text(resume), _candidate_text(context.candidate)) * 100),
                    critical_issues=len(critical),
                )
                resume = await asyncio.to_thread(
                    _run_resume_once, context, plan, repair_note, summarize_issues(issues)
                )
                resume = ensure_evidence_projects(
                    resume, context.evidence_projects, top_n=2
                )
            return resume

        async def generate_cover_letter(state: PipelineState):
            context = state.require("build_context")
            plan = build_tailoring_plan(
                context.candidate, context.job_analysis, context.ats_keywords, context.evidence
            )
            return await asyncio.to_thread(
                self.ai.run,
                "generate_cover_letter",
                {
                    "candidate_json": context.candidate_json(),
                    "job_description": context.job_description,
                    "keywords_json": context.keywords_json(),
                    "evidence_json": context.evidence_json(),
                    "verified_projects": context.evidence_projects_json(),
                    "tailoring_plan": plan.to_json(),
                    "humanizer_guidance": HUMANIZER_GUIDANCE,
                },
            )

        async def review_ats(state: PipelineState):
            resume = state.require("generate_resume")
            context = state.require("build_context")
            analysis = state.require("analyze_job")
            report = await asyncio.to_thread(
                self.ai.run,
                "review_ats",
                {
                    "resume_json": resume.model_dump_json(),
                    "job_analysis_json": analysis.model_dump_json(),
                    "evidence_json": context.evidence.model_dump_json(),
                },
            )
            return postprocess_ats_report(
                report, context.candidate, analysis, context.evidence
            )

        async def review_cover_letter(state: PipelineState):
            context = state.require("build_context")
            letter = state.require("generate_cover_letter")
            try:
                return await asyncio.to_thread(
                    self.ai.run,
                    "review_cover_letter",
                    {
                        "cover_letter_json": letter.model_dump_json(),
                        "candidate_json": context.candidate_json(),
                        "job_analysis_json": context.job_analysis_json(),
                    },
                )
            except AssertionError:
                return CoverLetterReviewModel()

        async def render_cv(state: PipelineState):
            resume = state.require("generate_resume")
            context = state.require("build_context")
            return await asyncio.to_thread(
                self.documents.compile,
                render_resume(resume, context.candidate, context.job_analysis.title),
                f"cv_{run_id}",
            )

        async def render_cover(state: PipelineState):
            context = state.require("build_context")
            letter = state.require("generate_cover_letter")
            return await asyncio.to_thread(
                self.documents.compile,
                render_cover_letter(letter, context.candidate),
                f"cover_letter_{run_id}",
            )

        async def response_builder(state: PipelineState):
            files = []
            evidence = state.require("discovery")
            result: dict[str, Any] = {
                "cv_pdf": None,
                "cover_letter_pdf": None,
                "cleaned_data": state.require("generate_resume").model_dump(mode="json")
                if "generate_resume" in state.snapshot()
                else None,
                "ats_report": None,
                "cover_letter_review": state.get("review_cover_letter").model_dump(mode="json")
                if state.get("review_cover_letter") is not None
                else None,
                "enrichment_data": [chunk.raw for chunk in evidence.chunks],
                "warnings": evidence.warnings,
                "source_status": [source.model_dump(mode="json") for source in evidence.sources],
            }
            if state.get("review_ats") is not None:
                result["ats_report"] = state.get("review_ats").model_dump(mode="json")
            if state.get("render_cv") is not None:
                result["cv_pdf"] = state.get("render_cv").name
                files.append(result["cv_pdf"])
            if state.get("render_cover") is not None:
                result["cover_letter_pdf"] = state.get("render_cover").name
                files.append(result["cover_letter_pdf"])
            if files:
                result["document_token"] = create_document_token(files)
            return result

        nodes = [
            Node("validate_candidate", validate_candidate, output_model=Candidate),
            Node("analyze_job", analyze_job, output_model=JobAnalysis, kind="ai", agent="Job Description Analyst"),
            Node("extract_ats_keywords", extract_keywords, output_model=ATSKeywordModel, kind="ai", agent="ATS Keyword Extraction Specialist"),
            Node("discovery", discover, ("extract_ats_keywords",), CandidateEvidenceModel, kind="discovery", worker="coordinator"),
            Node("build_context", build_context, ("validate_candidate", "analyze_job", "extract_ats_keywords", "discovery"), kind="service"),
            Node("generate_resume", generate_resume, ("build_context",), ResumeModel, kind="ai", agent="Resume Generation Specialist"),
            Node("review_ats", review_ats, ("generate_resume", "build_context"), ATSReport, kind="ai", agent="ATS Review Specialist"),
        ]
        if output_type in ("cv", "both"):
            nodes.extend([
                Node("render_cv", render_cv, ("generate_resume",), kind="render"),
            ])
        if output_type in ("cover_letter", "both"):
            nodes.extend([
                Node("generate_cover_letter", generate_cover_letter, ("build_context",), CoverLetter, kind="ai", agent="Cover Letter Specialist"),
                Node("review_cover_letter", review_cover_letter, ("generate_cover_letter",), CoverLetterReviewModel, kind="ai", agent="Cover Letter Review Specialist"),
                Node("render_cover", render_cover, ("generate_cover_letter",), kind="render"),
            ])
        response_deps = tuple(node.id for node in nodes if node.id not in {"validate_candidate", "analyze_job", "extract_ats_keywords", "discovery", "build_context"})
        nodes.append(Node("response_builder", response_builder, response_deps))

        initial = {
            "candidate_data": candidate_data,
            "job_description": job_description,
            "portfolio_links": links,
            "notes": notes,
        }
        state = await execute_dag(nodes, initial)
        return state.require("response_builder")

    def generate(self, *args, **kwargs) -> dict[str, Any]:
        """Synchronous compatibility facade for tests, CLI, and old callers."""
        return asyncio.run(self.generate_async(*args, **kwargs))
