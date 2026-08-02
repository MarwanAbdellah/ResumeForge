import pytest
from pydantic import ValidationError

from models.schemas import ATSReport, Candidate, Certification, JobAnalysis, Skill


def test_candidate_normalizes_legacy_categorized_skills_to_typed_models():
    candidate = Candidate(
        name="Jane Doe",
        skills={"languages": ["Python", ""], "tools": ["FastAPI"]},
        certifications=[{"name": "AWS Certified", "issuer": "AWS"}],
    )

    assert candidate.skills == [
        Skill(name="Python", category="languages"),
        Skill(name="FastAPI", category="tools"),
    ]
    assert isinstance(candidate.certifications[0], Certification)


def test_nested_resume_data_rejects_untyped_extra_fields():
    with pytest.raises(ValidationError):
        Candidate(certifications=[{"name": "AWS", "metadata": {"raw": True}}])
    with pytest.raises(ValidationError):
        Candidate(skills={"tools": {"name": "FastAPI"}})


def test_job_analysis_and_ats_report_validate_ranges_and_nested_feedback():
    analysis = JobAnalysis(required_skills=["Python"], resume_strategy=["Lead with API delivery"])
    report = ATSReport(
        score=84,
        actionable_suggestions=[{"priority": "high", "action": "Add Docker evidence"}],
    )

    assert analysis.required_skills == ["Python"]
    assert report.actionable_suggestions[0].action == "Add Docker evidence"

    with pytest.raises(ValidationError):
        ATSReport(score=101)


def test_url_fields_are_json_serializable_for_crewai_storage():
    candidate = Candidate(
        name="Jane",
        links={"github": "https://github.com/jane"},
        projects=[{"name": "Project", "url": "https://example.com/project"}],
    )
    payload = candidate.model_dump()
    assert payload["links"]["github"] == "https://github.com/jane"
    assert payload["projects"][0]["url"] == "https://example.com/project"
