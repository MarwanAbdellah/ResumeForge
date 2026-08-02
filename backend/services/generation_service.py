"""Application generation workflow using structured models only."""

import json
import uuid
from time import perf_counter
from typing import Any

from models.schemas import ATSReport, Candidate, CoverLetter, JobAnalysis
from renderers import render_cover_letter, render_resume
from security import create_document_token
from tools.link_fetcher import fetch_portfolio_links
from observability.events import emit_event, stage_span
from observability.metrics import metrics

from .ai_service import AIService
from .document_service import DocumentService


class GenerationService:
    def __init__(self, ai: AIService | None = None, documents: DocumentService | None = None):
        self.ai = ai or AIService()
        self.documents = documents or DocumentService()

    def analyze_job(self, job_description: str) -> JobAnalysis:
        return self.ai.run("analyze_job", {"job_description": job_description})

    def structure(self, extracted_text: str) -> Candidate:
        return self.ai.run("structure_resume", {"source_text": extracted_text})

    def ats_check(self, candidate: Candidate, job_description: str) -> ATSReport:
        analysis = self.analyze_job(job_description)
        return self.ai.run("review_ats", {
            "candidate_json": candidate.model_dump_json(),
            "job_analysis": analysis.model_dump_json(),
        })

    def generate(self, candidate_data: dict[str, Any], job_description: str, output_type: str, notes: str = "", portfolio_links: list[str] | None = None) -> dict[str, Any]:
        run_started = perf_counter()
        with stage_span("candidate_validation", component="GenerationService"):
            candidate = Candidate.model_validate(candidate_data)
        with stage_span("job_analysis", component="GenerationService"):
            analysis = self.analyze_job(job_description)
        with stage_span("portfolio_enrichment", component="PortfolioService", link_count=len(portfolio_links or [])):
            verified_portfolio = fetch_portfolio_links(portfolio_links or []) if portfolio_links else []
        if verified_portfolio:
            candidate.portfolio = [*candidate.portfolio, *[
                {"platform": item.get("platform", ""), "source_url": item.get("url"), "evidence": json.dumps(item), "verified": True}
                for item in verified_portfolio
            ]]
        with stage_span("resume_optimization", component="GenerationService"):
            optimized = self.ai.run("optimize_resume", {
                "candidate_json": candidate.model_dump_json(),
                "job_analysis": analysis.model_dump_json(),
            })
        with stage_span("ats_review", component="GenerationService"):
            ats_report: ATSReport = self.ai.run("review_ats", {
                "candidate_json": optimized.model_dump_json(),
                "job_analysis": analysis.model_dump_json(),
            })
        result: dict[str, Any] = {"cv_pdf": None, "cover_letter_pdf": None, "cleaned_data": optimized.model_dump(mode="json"), "ats_report": ats_report.model_dump(mode="json"), "enrichment_data": verified_portfolio}
        run_id = uuid.uuid4().hex[:8]
        filenames = []
        if output_type in ("cv", "both"):
            with stage_span("resume_render_and_compile", component="DocumentService"):
                cv_path = self.documents.compile(render_resume(optimized), f"cv_{run_id}")
            result["cv_pdf"] = cv_path.name
            filenames.append(cv_path.name)
        if output_type in ("cover_letter", "both"):
            with stage_span("cover_letter_generation", component="GenerationService"):
                letter: CoverLetter = self.ai.run("generate_cover_letter", {
                    "candidate_json": optimized.model_dump_json(),
                    "job_description": job_description,
                })
            with stage_span("cover_letter_render_and_compile", component="DocumentService"):
                letter_path = self.documents.compile(render_cover_letter(letter, optimized), f"cover_letter_{run_id}")
            result["cover_letter_pdf"] = letter_path.name
            filenames.append(letter_path.name)
        if filenames:
            result["document_token"] = create_document_token(filenames)
        metrics.observe("resumeforge_generation_duration", (perf_counter() - run_started) * 1000, output_type=output_type)
        emit_event("generation", "completed", duration_ms=round((perf_counter() - run_started) * 1000), output_type=output_type)
        return result
