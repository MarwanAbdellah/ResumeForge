from models.pipeline import ATSKeywordModel, CandidateEvidenceModel, EvidenceChunk, ResumeModel
from models.schemas import Candidate, JobAnalysis
from services.tailoring import (
    build_tailoring_plan,
    normalize_requirements,
    summarize_issues,
    token_overlap,
    validate_generated_resume,
)


def make_candidate() -> Candidate:
    return Candidate(
        name="Jane Doe",
        summary="Data analyst with Python and SQL.",
        skills=[
            {"name": "Python", "category": "languages"},
            {"name": "Pandas", "category": "languages"},
            {"name": "SQL", "category": "tools"},
        ],
        experience=[
            {
                "title": "Data Analyst",
                "company": "Acme",
                "dates": "2021-Present",
                "bullets": ["Built interactive Tableau dashboards"],
            }
        ],
        projects=[
            {
                "name": "Sales Dashboard",
                "description": "Interactive Tableau dashboards",
                "url": "https://github.com/jane/sales-dashboard",
            }
        ],
        links={"github": "https://github.com/jane"},
    )


def make_job_analysis() -> JobAnalysis:
    return JobAnalysis(
        title="Junior Data Analyst",
        required_skills=["Python", "Python Pandas", "dashboarding", "SQL"],
        technical_stack=["Power BI"],
        preferred_skills=[],
    )


class TestNormalization:
    def test_alias_expansion(self):
        normalized = normalize_requirements(["Python Pandas", "dashboarding", "SQL"])
        assert "Python" in normalized
        assert "Pandas" in normalized
        assert "Power BI" in normalized
        assert "Tableau" in normalized
        assert "SQL" in normalized


class TestTailoringPlan:
    def test_plan_classifies_requirements(self):
        candidate = make_candidate()
        jd = make_job_analysis()
        plan = build_tailoring_plan(candidate, jd)

        assert "Python" in plan.confirmed
        assert "Pandas" in plan.confirmed
        assert "SQL" in plan.confirmed
        assert "Tableau" in plan.confirmed  # dashboards in prose
        assert "Power BI" in plan.must_not_claim  # never mentioned by the candidate

    def test_external_evidence_lands_in_verified_external(self):
        candidate = make_candidate()
        jd = make_job_analysis()
        evidence = CandidateEvidenceModel(
            chunks=[
                EvidenceChunk(
                    source="github",
                    platform="github",
                    title="ArabMedRAG",
                    summary="Medical RAG system built with Python and Pandas",
                    technologies=["Python", "Pandas", "LLM"],
                    verified=True,
                )
            ]
        )
        plan = build_tailoring_plan(candidate, jd, ATSKeywordModel(), evidence)
        assert plan.verified_external_evidence  # ArabMedRAG surfaces as evidence

    def test_plan_json_round_trip(self):
        plan = build_tailoring_plan(make_candidate(), make_job_analysis())
        payload = plan.to_json()
        assert "confirmed" in payload
        assert "must_not_claim" in payload
        assert "Power BI" in payload


class TestValidation:
    def make_resume(self, **overrides) -> ResumeModel:
        defaults = {
            "name": "Jane Doe",
            "summary": "Data analyst specializing in Python, Pandas and SQL dashboards.",
            "experience": [
                {
                    "title": "Data Analyst",
                    "company": "Acme",
                    "dates": "2021-Present",
                    "bullets": ["Built interactive Tableau dashboards for executives"],
                }
            ],
            "projects": [
                {
                    "name": "Sales Dashboard",
                    "description": "Tableau dashboards",
                    "url": "https://github.com/jane/sales-dashboard",
                }
            ],
            "skills": [{"name": "Python"}, {"name": "Pandas"}, {"name": "SQL"}],
        }
        defaults.update(overrides)
        return ResumeModel.model_validate(defaults)

    def test_valid_resume_passes_cleanly(self):
        plan = build_tailoring_plan(make_candidate(), make_job_analysis())
        resume = self.make_resume()
        issues = validate_generated_resume(resume, make_candidate(), plan)
        assert all(not messages for messages in issues.values())

    def test_echoing_summary_is_caught(self):
        candidate = make_candidate()
        plan = build_tailoring_plan(candidate, make_job_analysis())
        resume = self.make_resume(summary=candidate.summary)  # verbatim echo
        issues = validate_generated_resume(resume, candidate, plan)
        assert issues["summary_echo"]

    def test_inventing_must_not_claim_skill_is_caught(self):
        plan = build_tailoring_plan(make_candidate(), make_job_analysis())
        resume = self.make_resume(
            skills=[{"name": "Python"}, {"name": "Pandas"}, {"name": "SQL"}, {"name": "Power BI"}]
        )
        issues = validate_generated_resume(resume, make_candidate(), plan)
        assert any("Power BI" in message for message in issues["invented_skills"])

    def test_dropped_dates_and_urls_are_caught(self):
        candidate = make_candidate()
        plan = build_tailoring_plan(candidate, make_job_analysis())
        resume = self.make_resume(
            experience=[
                {
                    "title": "Data Analyst",
                    "company": "Acme",
                    "dates": "2020-2021",  # changed from 2021-Present
                    "bullets": ["Built interactive Tableau dashboards for executives"],
                }
            ],
            projects=[
                {"name": "Sales Dashboard", "description": "Tableau dashboards"}  # url dropped
            ],
        )
        issues = validate_generated_resume(resume, candidate, plan)
        assert issues["fact_integrity"]
        assert any("2021-Present" in message for message in issues["fact_integrity"])
        assert any("github.com/jane/sales-dashboard" in message for message in issues["fact_integrity"])

    def test_token_overlap_detects_high_echo(self):
        text = "Data analyst with Python and SQL building dashboards"
        assert token_overlap(text, text) == 1.0
        assert token_overlap("Completely different content here", text) < 0.5

    def test_summarize_issues_formats_messages(self):
        issues = {"invented_skills": ["Resume lists unsupported skill 'X'."]}
        assert "X" in summarize_issues(issues)
