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


TASKS_CONFIG = Path(__file__).parent.parent / "config" / "tasks.yaml"


def load_task_config() -> dict:
    with TASKS_CONFIG.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


OUTPUT_MODELS = {
    "extract_resume": Candidate,
    "structure_resume": Candidate,
    "analyze_job": JobAnalysis,
    "optimize_resume": Candidate,
    "generate_cover_letter": CoverLetter,
    "review_ats": ATSReport,
    "analyze_portfolio": PortfolioEvidence,
}

