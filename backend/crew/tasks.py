"""Declarative CrewAI task factory."""

from pathlib import Path
import yaml

from models.schemas import (
    ATSReport,
    Candidate,
    CoverLetter,
    JobAnalysis,
    PortfolioEvidence,
)
from models.pipeline import ATSKeywordModel, CoverLetterReviewModel, ResumeModel


TASKS_CONFIG = Path(__file__).parent.parent / "config" / "tasks.yaml"


def load_task_config() -> dict:
    with TASKS_CONFIG.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


OUTPUT_MODELS = {
    "extract_resume": Candidate,
    "structure_resume": Candidate,
    "analyze_job": JobAnalysis,
    "extract_ats_keywords": ATSKeywordModel,
    "generate_resume": ResumeModel,
    "generate_cover_letter": CoverLetter,
    "review_ats": ATSReport,
    "review_cover_letter": CoverLetterReviewModel,
    "analyze_portfolio": PortfolioEvidence,
}
