from models.pipeline import CandidateEvidenceModel, EvidenceChunk
from models.schemas import Candidate, InquiryQuestion, JobAnalysis
from services.gap_service import (
    build_inquiry_questions,
    canonical_keyword,
    classification_summary,
    classify_skill,
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
                "bullets": [
                    "Built interactive dashboards in Tableau",
                    "Analyzed sales data with Python and SQL",
                ],
            }
        ],
        education=[
            {
                "school": "DataCamp",
                "degree": "Diploma",
                "field": "Data Analytics",
                "details": "Advanced Data Analytics Diploma",
                "dates": "2020",
            }
        ],
        projects=[
            {
                "name": "ArabMedRAG",
                "description": "LLM retrieval over medical data with Python",
                "bullets": ["Fine-tuned models with Hugging Face"],
            }
        ],
        links={"github": "https://github.com/jane"},
    )


def make_job_analysis() -> JobAnalysis:
    return JobAnalysis(
        title="Junior Data Analyst",
        required_skills=["Python", "Pandas", "Tableau", "Power BI", "Data Analytics", "Machine Learning"],
        preferred_skills=["pivot tables"],
        technical_stack=[],
    )


def make_evidence() -> CandidateEvidenceModel:
    return CandidateEvidenceModel(
        chunks=[
            EvidenceChunk(
                source="github",
                platform="github",
                title="ArabMedRAG",
                summary="Medical RAG system",
                technologies=["Python", "Machine Learning", "LLM", "Pandas"],
                verified=True,
            )
        ]
    )


class TestClassification:
    def test_confirmed_skills_are_not_interviewed(self):
        candidate = make_candidate()
        jd = make_job_analysis()

        questions = build_inquiry_questions(candidate, jd)
        keywords = {q.keyword for q in questions}

        assert "Python" not in keywords
        assert "Pandas" not in keywords
        assert "Tableau" not in keywords  # dashboards in experience are related evidence

    def test_questions_are_typed_and_never_undefined(self):
        candidate = make_candidate()
        jd = make_job_analysis()

        questions = build_inquiry_questions(candidate, jd)
        assert len(questions) > 0
        for q in questions:
            assert isinstance(q, InquiryQuestion)
            assert q.keyword and q.question

    def test_classification_recognizes_related_evidence(self):
        candidate = make_candidate()
        jd = make_job_analysis()

        # Tableau is recognized through "dashboards" in experience bullets.
        tableau = classify_skill("Tableau", candidate)
        assert tableau.classification == "confirmed_experience"

        # Data Analytics appears only in the education/diploma scope.
        analytics = classify_skill("Data Analytics", candidate)
        assert analytics.classification == "coursework_only"

        # ML is confirmed through external GitHub evidence (ArabMedRAG).
        ml = classify_skill("Machine Learning", candidate, make_evidence())
        assert ml.classification == "confirmed_experience"

        # Power BI only has related (dashboarding) evidence, not confirmation.
        power_bi = classify_skill("Power BI", candidate)
        assert power_bi.classification == "basic_knowledge"

    def test_classification_summary_covers_all_five_levels(self):
        candidate = Candidate(
            name="Jane",
            skills=[{"name": "Python"}],
            experience=[
                {
                    "title": "Analyst",
                    "bullets": [
                        "Used pandas",
                        "Built dashboards",
                        "Interested in learning automation",
                    ],
                }
            ],
            education=[{"field": "Statistics", "degree": "BSc"}],
        )
        jd = JobAnalysis(
            required_skills=["Python", "Tableau"],
            technical_stack=["Statistics"],
            preferred_skills=["Power BI", "docker", "automation"],
        )
        summary = classification_summary(candidate, jd)
        levels = {entry["classification"] for entry in summary}
        assert "confirmed_experience" in levels  # Python
        assert "basic_knowledge" in levels  # Tableau / Power BI via dashboards
        assert "coursework_only" in levels  # Statistics via BSc
        assert "learning_interest" in levels  # automation via learning intent
        assert "no_experience" in levels  # docker


class TestQuestionSynthesis:
    def test_llm_string_questions_are_converted_to_typed_objects(self):
        candidate = make_candidate()
        jd = make_job_analysis()
        report = {
            "score": 60,
            "inquiry_questions": ["Have you used Power BI in a real project?"],
        }

        questions = build_inquiry_questions(candidate, jd, report)
        power_bi = [q for q in questions if q.keyword == "Power BI"]
        assert len(power_bi) == 1
        assert "Power BI" in power_bi[0].question

    def test_deduplicates_existing_and_deterministic_questions(self):
        candidate = make_candidate()
        jd = make_job_analysis()
        report = {
            "inquiry_questions": [
                {"keyword": "Power BI", "question": "Any Power BI exposure?"},
            ]
        }

        questions = build_inquiry_questions(candidate, jd, report)
        power_bi = [q for q in questions if q.keyword == "Power BI"]
        assert len(power_bi) == 1

    def test_canonical_keyword_strips_jd_phrasing(self):
        assert canonical_keyword("Familiarity with Power BI") == "Power BI"
        assert canonical_keyword("experience with Tableau") == "Tableau"
        assert canonical_keyword("working knowledge of SQL") == "SQL"

    def test_power_bi_question_deduplicated_across_phrasings(self):
        candidate = make_candidate()  # has dashboards but no Power BI
        jd = JobAnalysis(
            required_skills=["Power BI", "Familiarity with Power BI"],
            technical_stack=[],
        )
        questions = build_inquiry_questions(candidate, jd)
        power_bi = [q for q in questions if q.keyword == "Power BI"]
        assert len(power_bi) == 1
