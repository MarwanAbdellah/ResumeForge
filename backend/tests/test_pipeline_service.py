from pathlib import Path

from models.schemas import ATSReport, Candidate, CoverLetter, JobAnalysis
from services.generation_service import GenerationService


class FakeAI:
    def run(self, task_name, inputs):
        if task_name == "analyze_job":
            return JobAnalysis(title="Engineer", required_skills=["Python"])
        if task_name == "optimize_resume":
            return Candidate.model_validate_json(inputs["candidate_json"])
        if task_name == "generate_cover_letter":
            return CoverLetter(salutation="Dear Hiring Manager,", paragraphs=["I am applying with relevant experience."], signoff="Sincerely")
        if task_name == "review_ats":
            return ATSReport(score=80, verdict="Strong Match")
        raise AssertionError(task_name)


class FakeDocuments:
    def __init__(self, root: Path):
        self.root = root

    def compile(self, tex_source, output_name):
        assert "<html" not in tex_source.lower()
        path = self.root / f"{output_name}.pdf"
        path.write_bytes(b"pdf")
        return path


def test_generation_uses_structured_models_and_deterministic_renderer(tmp_path):
    service = GenerationService(FakeAI(), FakeDocuments(tmp_path))
    result = service.generate(
        {"name": "Jane Doe", "email": "jane@example.com"},
        "Python engineer",
        "both",
    )
    assert result["cv_pdf"].startswith("cv_")
    assert result["cover_letter_pdf"].startswith("cover_letter_")
    assert result["document_token"]
