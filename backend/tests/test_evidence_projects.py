from models.pipeline import (
    ATSKeywordModel,
    CandidateEvidenceModel,
    EvidenceChunk,
    ResumeModel,
)
from models.schemas import Project
from services.evidence_projects import build_external_projects, ensure_evidence_projects

TABLEAU_URL = "https://public.tableau.com/app/profile/marwan/viz/UdemyCourseAnalysisDashboard/Dashboard1"


def make_evidence() -> CandidateEvidenceModel:
    return CandidateEvidenceModel(
        chunks=[
            EvidenceChunk(
                source="github",
                platform="github",
                title="Udemy-Finance-Accounting-Course-Analysis",
                url="https://github.com/marwan/Udemy-Finance-Accounting-Course-Analysis",
                summary=(
                    "Analyzed Udemy finance and accounting courses with Python, Pandas and "
                    "SQL. Built an interactive dashboard with Tableau."
                ),
                technologies=["Python", "Pandas", "SQL"],
                verified=True,
                raw={"related_links": [TABLEAU_URL]},
            ),
            EvidenceChunk(
                source="github",
                platform="github",
                title="ArabMedRAG",
                url="https://github.com/marwan/ArabMedRAG",
                summary="Arabic medical chatbot built with Python and LLMs.",
                technologies=["Python", "LLM"],
                verified=True,
                raw={"related_links": []},
            ),
        ]
    )


class TestBuildExternalProjects:
    def test_ranks_job_relevant_project_first_and_keeps_demo_link(self):
        keywords = ATSKeywordModel(
            required_keywords=["Data Analysis"], technical_terms=["Pandas", "Dashboard"]
        )
        projects = build_external_projects(make_evidence(), keywords)
        assert projects[0].name == "Udemy-Finance-Accounting-Course-Analysis"
        assert projects[0].url == "https://github.com/marwan/Udemy-Finance-Accounting-Course-Analysis"
        assert projects[0].demo_url == TABLEAU_URL
        assert "Python" in projects[0].technologies
        assert projects[0].bullets

    def test_deduplicates_by_title(self):
        evidence = make_evidence()
        evidence.chunks.append(
            evidence.chunks[0].model_copy(update={"url": "https://example.com/dup"})
        )
        projects = build_external_projects(evidence, ATSKeywordModel())
        assert len(projects) == 2


class TestEnsureEvidenceProjects:
    def test_inserts_missing_relevant_project(self):
        resume = ResumeModel(
            name="Marwan", summary="Data analyst", projects=[Project(name="Other Project")]
        )
        out = ensure_evidence_projects(
            resume, build_external_projects(make_evidence(), ATSKeywordModel()), top_n=1
        )
        assert out.projects[0].name == "Udemy-Finance-Accounting-Course-Analysis"
        assert out.projects[0].url.startswith("https://github.com/marwan/")
        assert out.projects[0].demo_url == TABLEAU_URL
        assert len(out.projects) == 2

    def test_patches_existing_project_links_from_evidence(self):
        resume = ResumeModel(
            name="Marwan",
            summary="Data analyst",
            projects=[
                Project(
                    name="Udemy-Finance-Accounting-Course-Analysis",
                    url="https://github.com/marwan",  # profile link, not repo
                )
            ],
        )
        out = ensure_evidence_projects(
            resume, build_external_projects(make_evidence(), ATSKeywordModel()), top_n=0
        )
        project = out.projects[0]
        assert project.url == "https://github.com/marwan/Udemy-Finance-Accounting-Course-Analysis"
        assert project.demo_url == TABLEAU_URL
        assert len(out.projects) == 1
