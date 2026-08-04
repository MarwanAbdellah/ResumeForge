from models.pipeline import CandidateEvidenceModel, EvidenceChunk
from models.schemas import ATSReport, Candidate, JobAnalysis
from services.ats_postprocess import build_grounded_suggestions, postprocess_ats_report


def make_candidate() -> Candidate:
    return Candidate(
        name="Jane Doe",
        summary="Data analyst with Python and SQL.",
        skills=[
            {"name": "Python", "category": "languages"},
            {"name": "Pandas", "category": "languages"},
            {"name": "SQL", "category": "tools"},
            {"name": "Tableau", "category": "tools"},
        ],
        experience=[
            {
                "title": "Data Analyst",
                "company": "Acme",
                "dates": "2021-Present",
                "bullets": ["Built interactive dashboards in Tableau"],
            }
        ],
    )


def test_grounded_suggestions_never_claim_unconfirmed_skills():
    candidate = make_candidate()
    jd = JobAnalysis(required_skills=["Power BI", "SQL"], technical_stack=[])
    report = ATSReport(
        score=50,
        suggestions=[
            "Explicitly mention Power BI or Tableau experience if applicable to meet the technical stack requirements.",
            "Include specific examples of Data Cleaning and Reporting in your project descriptions.",
        ],
    )

    out = postprocess_ats_report(report, candidate, jd)

    # The speculative "explicitly mention Power BI" suggestion is filtered out.
    assert not any("explicitly mention" in s.lower() for s in out.suggestions)
    # A grounded Power BI suggestion remains (it is genuinely unconfirmed).
    assert any("Power BI" in s for s in out.suggestions)
    # Useful role-specific suggestion is kept.
    assert any("Data Cleaning" in s for s in out.suggestions)


def test_postprocess_dedupes_power_bi_questions():
    candidate = make_candidate()
    jd = JobAnalysis(required_skills=["Power BI", "Familiarity with Power BI"], technical_stack=[])
    report = ATSReport(
        score=50,
        inquiry_questions=[
            {"keyword": "Power BI", "question": "Have you used Power BI?"},
            {"keyword": "Familiarity with Power BI", "question": "Have you used Familiarity with Power BI?"},
        ],
    )

    out = postprocess_ats_report(report, candidate, jd)
    power_bi = [q for q in out.inquiry_questions if q.keyword == "Power BI"]
    assert len(power_bi) == 1


def test_grounded_suggestions_skip_confirmed_skills():
    candidate = make_candidate()
    plan_suggestions = build_grounded_suggestions(
        __import__("services.tailoring", fromlist=["build_tailoring_plan"]).build_tailoring_plan(
            candidate, JobAnalysis(required_skills=["Tableau", "SQL", "Power BI"], technical_stack=[])
        ),
        candidate,
    )
    text = "\n".join(plan_suggestions).lower()
    assert "tableau" not in text  # Tableau is confirmed
    assert "sql" not in text  # SQL is confirmed
    assert "power bi" in text  # Power BI is not
