from models.pipeline import ResumeModel
from models.schemas import Candidate, Certification, Experience, Language, Project, Skill
from renderers import render_resume
from renderers.latex import build_skill_groups


def test_resume_renderer_uses_validated_data_only():
    tex = render_resume(Candidate(
        name="Ada Lovelace",
        email="ada@example.com",
        experience=[Experience(title="Engineer", company="Analytical Engines", bullets=["Built 100% safe code & tests."])],
    ))
    assert "Ada Lovelace" in tex
    assert r"100\% safe code \& tests." in tex
    assert "Marwan" not in tex


def test_generated_resume_uses_candidate_identity_and_links():
    candidate = Candidate(
        name="Jane Doe",
        email="jane@example.com",
        phone="+1 555 0100",
        location="Cairo, Egypt",
        summary="Factual candidate summary.",
        links={"LinkedIn": "https://linkedin.com/in/jane", "GitHub": "https://github.com/jane"},
    )
    resume = ResumeModel(
        name="ResumeModel",
        summary="An optimized, ATS-ready resume targeted at a specific role.\nDistinct from CandidateModel",
    )

    tex = render_resume(resume, candidate, "Machine Learning Engineer")

    assert "Jane Doe" in tex
    assert "ResumeModel" not in tex
    assert "jane@example.com" in tex
    assert "Machine Learning Engineer" in tex
    assert "https://linkedin.com/in/jane" in tex
    assert "Factual candidate summary." in tex


def test_skills_render_grouped_not_raw_categories():
    candidate = Candidate(
        name="Jane",
        skills=[
            Skill(name="Python", category="Data & Cloud"),
            Skill(name="Pandas", category="Data & Cloud"),
            Skill(name="Tableau", category="Data & Cloud"),
            Skill(name="LangChain", category="GenAI & Agents"),
            Skill(name="Communication", category="Soft Skills"),
        ],
    )
    tex = render_resume(candidate)
    # Raw category labels must not appear next to every skill.
    assert "(Data & Cloud)" not in tex
    # Friendly group headers are rendered (ampersands are LaTeX-escaped).
    assert r"Data \& Analytics" in tex
    assert r"GenAI \& Agents" in tex
    assert "Productivity" in tex
    assert "Python, Pandas, Tableau" in tex


def test_project_links_render_as_labelled_hyperlinks():
    candidate = Candidate(
        name="Jane",
        projects=[
            Project(
                name="Udemy-Finance-Accounting-Course-Analysis",
                url="https://github.com/jane/Udemy-Finance-Accounting-Course-Analysis",
                demo_url="https://public.tableau.com/app/profile/jane/viz/Dashboard1",
                description="Finance course analytics with Python and Pandas.",
                bullets=["Built an interactive dashboard"],
            )
        ],
    )
    tex = render_resume(candidate)
    assert r"\href{ https://github.com/jane/Udemy-Finance-Accounting-Course-Analysis }" in tex
    assert r"\href{ https://public.tableau.com/app/profile/jane/viz/Dashboard1 }" in tex
    assert "Dashboard" in tex
    # The raw repository URL should not be printed as plain text in the heading.
    assert "https://github.com/jane/Udemy-Finance-Accounting-Course-Analysis" not in tex.replace(r"\href{ https://github.com/jane/Udemy-Finance-Accounting-Course-Analysis }", "").replace(r"\myuline", "")


def test_build_skill_groups_orders_by_first_appearance_and_dedupes():
    groups = build_skill_groups(
        [
            {"name": "LangChain", "category": "agents"},
            {"name": "Python", "category": "programming"},
            {"name": "Python", "category": "programming"},
            {"name": "Tableau", "category": "data"},
        ]
    )
    names = [group["name"] for group in groups]
    assert names[0] == "GenAI & Agents"  # LangChain appears first in the source order
    skills = [group["skills"] for group in groups if group["name"] == "Programming & Data"][0]
    assert skills == ["Python"]
