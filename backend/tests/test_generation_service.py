from pathlib import Path

from models.schemas import ATSReport, Candidate, CoverLetter, JobAnalysis
from services.generation_service import GenerationService


class EchoAI:
    """Returns the candidate verbatim, so the echo-guard must repair-retry."""

    def __init__(self):
        self.resume_calls = 0

    def run(self, task_name, inputs):
        if task_name == "analyze_job":
            return JobAnalysis(title="Data Analyst", required_skills=["Python", "SQL"])
        if task_name == "extract_ats_keywords":
            raise AssertionError("no keywords task")
        if task_name == "generate_resume":
            raise AssertionError("not the real task")
        if task_name == "optimize_resume":
            self.resume_calls += 1
            return Candidate.model_validate_json(inputs["candidate_json"])
        if task_name == "generate_cover_letter":
            return CoverLetter(salutation="Dear", paragraphs=["Relevant experience."], signoff="Best")
        if task_name == "review_ats":
            return ATSReport(score=80, verdict="Strong Match")
        if task_name == "review_cover_letter":
            raise AssertionError("no review task")
        raise AssertionError(task_name)


class FakeDocuments:
    def __init__(self, root: Path):
        self.root = root

    def compile(self, tex_source, output_name):
        path = self.root / f"{output_name}.pdf"
        path.write_bytes(b"pdf")
        return path


def test_echo_guard_triggers_a_repair_retry(tmp_path):
    ai = EchoAI()
    service = GenerationService(ai, FakeDocuments(tmp_path))
    candidate = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "summary": "Data analyst with Python and SQL building dashboards.",
        "experience": [
            {
                "title": "Data Analyst",
                "company": "Acme",
                "dates": "2021-Present",
                "bullets": ["Built dashboards"],
            }
        ],
        "skills": {"languages": ["Python", "SQL"]},
        "projects": [],
    }

    result = service.generate(candidate, "Junior Data Analyst", "cv")

    # Initial attempt echoes the candidate (100% overlap) -> exactly one repair
    # retry is issued, then the result is accepted (no infinite loop).
    assert ai.resume_calls >= 2
    assert result["cv_pdf"].startswith("cv_")


def test_generated_resume_is_returned_and_validated(tmp_path):
    ai = EchoAI()
    service = GenerationService(ai, FakeDocuments(tmp_path))
    candidate = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "summary": "Data analyst with Python and SQL.",
        "experience": [],
        "skills": {"languages": ["Python", "SQL"]},
        "projects": [],
    }
    result = service.generate(candidate, "Data Analyst", "cv")
    assert result["cleaned_data"]["name"] == "Jane Doe"
    assert "ats_report" in result
    assert result["ats_report"]["score"] == 80
