"""Deterministic inquiry-question synthesis for the pre-generation interview.

Builds typed ``InquiryQuestion`` objects from an ATS report, converts any
LLM-returned strings into the typed shape, appends deterministic questions for
skills the candidate has not confirmed, and deduplicates. Every skill is
classified into one of five levels instead of a binary yes/no.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from models.pipeline import CandidateEvidenceModel
from models.schemas import ATSReport, Candidate, InquiryQuestion, JobAnalysis

CONFIRMED_EXPERIENCE = "confirmed_experience"
BASIC_KNOWLEDGE = "basic_knowledge"
COURSEWORK_ONLY = "coursework_only"
NO_EXPERIENCE = "no_experience"
LEARNING_INTEREST = "learning_interest"

CLASSIFICATION_LABELS = {
    CONFIRMED_EXPERIENCE: "confirmed experience",
    BASIC_KNOWLEDGE: "basic knowledge",
    COURSEWORK_ONLY: "coursework only",
    NO_EXPERIENCE: "no experience",
    LEARNING_INTEREST: "learning interest",
}

# Leading JD phrasing that must not leak into a canonical skill keyword.
PHRASE_PREFIXES = (
    "familiarity with ",
    "experience with ",
    "strong experience with ",
    "hands-on experience with ",
    "working knowledge of ",
    "knowledge of ",
    "understanding of ",
    "solid understanding of ",
    "proficiency in ",
    "proficient in ",
    "experience in ",
    "ability to use ",
    "familiarity of ",
)

CANONICAL_SKILLS = {
    "power bi": "Power BI",
    "tableau": "Tableau",
    "excel": "Excel",
    "python": "Python",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "sql": "SQL",
    "r": "R",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "deep learning": "Deep Learning",
    "data analysis": "Data Analysis",
    "data analytics": "Data Analysis",
    "dashboarding": "Dashboarding",
    "reporting": "Reporting",
    "automation": "Automation",
    "docker": "Docker",
    "git": "Git",
    "github": "GitHub",
    "fastapi": "FastAPI",
    "react": "React",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "communication": "Communication",
    "teamwork": "Teamwork",
    "problem solving": "Problem Solving",
}


def normalize_keyword(value: str) -> str:
    """Strip JD phrasings like 'Familiarity with Power BI' -> 'Power BI'."""
    text = " ".join((value or "").strip().split())
    lower = text.lower()
    for prefix in PHRASE_PREFIXES:
        if lower.startswith(prefix):
            text = " ".join(text[len(prefix):].strip().split())
            break
    return text


def canonical_keyword(value: str) -> str:
    """Return a canonical, deduplicable keyword for a JD requirement."""
    norm = normalize_keyword(value)
    key = norm.lower()
    if key in CANONICAL_SKILLS:
        return CANONICAL_SKILLS[key]
    return norm

# Strong aliases: near-identical names. A match here means the skill itself.
STRONG_ALIASES: dict[str, list[str]] = {
    "python": ["python"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "sql": ["sql", "postgresql", "postgres", "mysql", "sqlite", "mssql"],
    "excel": ["excel"],
    "power bi": ["power bi", "powerbi", "power-bi"],
    "tableau": ["tableau"],
    "dashboarding": ["dashboarding"],
    "data analysis": ["data analysis", "data-analysis"],
    "data analytics": ["data analytics", "data-analytics"],
    "machine learning": ["machine learning", " ml "],
    "deep learning": ["deep learning"],
    "reporting": ["reporting"],
    "automation": ["automation", "automations"],
    "git": ["git"],
    "github": ["github"],
    "docker": ["docker", "dockerfile", "docker-compose"],
    "fastapi": ["fastapi", "fast api"],
    "react": ["react", "reactjs"],
    "javascript": ["javascript"],
    "typescript": ["typescript"],
    "communication": ["communication"],
    "teamwork": ["teamwork"],
    "problem solving": ["problem solving", "problem-solving"],
}

# Related-evidence terms: broader signals that a skill may be present through
# adjacent work (e.g. "dashboard" implies Power BI / Tableau exposure) but is
# NOT a confirmed match on its own.
RELATED_TERMS: dict[str, list[str]] = {
    "python": ["pandas", "numpy", "scikit", "fastapi", "django", "flask", "pyspark", "jupyter", "data analysis"],
    "pandas": ["data analysis", "dataframe", "data frames", "eda", "python"],
    "numpy": ["data analysis", "dataframe", "python"],
    "sql": ["database", "databases", "query", "queries"],
    "excel": ["pivot table", "pivot tables", "spreadsheet", "spreadsheets", "vba", "macros"],
    "power bi": ["dashboard", "dashboards", "power query", "dax", "visualization"],
    "tableau": ["dashboard", "dashboards", "data visualization"],
    "dashboarding": ["dashboard", "dashboards", "power bi", "tableau", "visualization"],
    "data analysis": ["pandas", "numpy", "analytics", "eda", "statistics", "statistical"],
    "data analytics": ["data analysis", "analytics", "pandas", "statistics"],
    "machine learning": ["tensorflow", "pytorch", "xgboost", "scikit", "model training", "prediction", "models"],
    "deep learning": ["tensorflow", "pytorch", "keras", "neural network", "cnn", "transformer"],
    "reporting": ["reports", "kpi", "metrics", "stakeholder"],
    "automation": ["automated", "scripting", "cron", "pipeline", "workflow"],
    "git": ["github", "version control", "pull request", "repository"],
    "github": ["git", "repository", "open source", "repo"],
    "docker": ["container", "containers", "compose"],
    "fastapi": ["rest api", "uvicorn", "endpoint"],
    "react": ["frontend", "front-end", "components"],
    "javascript": ["node", "npm", "react", "typescript"],
    "typescript": ["react", "type-safe"],
    "communication": ["presentation", "stakeholder", "collaboration"],
    "teamwork": ["team", "collaboration", "cross-functional", "agile", "scrum"],
    "problem solving": ["troubleshooting", "debugging", "root cause"],
}

LEARNING_KEYWORDS = (
    "learning", "studying", "self-study", "interested in", "currently learning",
    "course", "courses", "udemy", "coursera", "tutorial", "tutorials", "mooc",
    "training", "workshop", "bootcamp", "certificate", "certification",
)
COURSEWORK_KEYWORDS = (
    "diploma", "degree", "bachelor", "master", "bsc", "msc", "ba", "ma",
    "course", "courses", "module", "elective", "certificate", "certification",
    "field of study", "major", "minor", "semester",
)


@dataclass
class SkillAssessment:
    skill: str
    classification: str
    reasoning: str
    evidence_hits: list[str] = field(default_factory=list)


def _as_candidate(value: Candidate | dict | None) -> Candidate | None:
    if value is None:
        return None
    return value if isinstance(value, Candidate) else Candidate.model_validate(value)


def _as_job_analysis(value: JobAnalysis | dict | None) -> JobAnalysis | None:
    if value is None:
        return None
    return value if isinstance(value, JobAnalysis) else JobAnalysis.model_validate(value)


def _as_evidence(value: CandidateEvidenceModel | dict | None) -> CandidateEvidenceModel | None:
    if value is None:
        return None
    if isinstance(value, CandidateEvidenceModel):
        return value
    return CandidateEvidenceModel.model_validate(value)


def _raw_report_questions(report: ATSReport | dict | None) -> list[Any]:
    """Extract inquiry questions from a report model or raw dict.

    Tolerant of legacy payloads where the LLM returned plain strings instead of
    ``{keyword, question}`` objects.
    """
    if report is None:
        return []
    if isinstance(report, ATSReport):
        return list(report.inquiry_questions)
    if isinstance(report, dict):
        questions = report.get("inquiry_questions")
        if isinstance(questions, list):
            return questions
    return []


# ── Text corpus helpers ───────────────────────────────────────────────────

def _term_found(text: str, term: str) -> bool:
    """Match a term with soft word boundaries so short skills (R, SQL, ML)
    do not false-positive inside longer words."""
    if not term:
        return False
    needle = re.escape(term.strip().lower())
    # Multi-word terms still get word boundaries around the whole phrase.
    pattern = rf"(?<![a-z0-9]){needle}(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def candidate_corpus(candidate: Candidate | None) -> dict[str, list[str]]:
    """Split candidate content into scopes used for classification."""
    if candidate is None:
        return {"skills": [], "experience": [], "projects": [], "education": [], "achievements": []}

    skills = [s.name for s in candidate.skills if s.name]
    experience = []
    for entry in candidate.experience:
        experience.append(entry.title or "")
        experience.append(entry.company or "")
        experience.extend(b for b in entry.bullets if b)
    projects = []
    for project in candidate.projects:
        projects.append(project.name or "")
        projects.append(project.description or "")
        projects.extend(b for b in project.bullets if b)
    education = []
    for entry in candidate.education:
        education.extend(
            part
            for part in (entry.degree, entry.field, entry.school, entry.institution, entry.details)
            if part
        )
    achievements = [a.title for a in candidate.achievements if a.title]
    corpus = {
        "skills": skills,
        "experience": experience,
        "projects": projects,
        "education": education,
        "achievements": achievements,
    }
    if candidate.portfolio:
        portfolio = []
        for item in candidate.portfolio:
            portfolio.append(item.project_name or "")
            portfolio.append(item.evidence or "")
            portfolio.extend(item.technologies or [])
        corpus["projects"] = corpus["projects"] + portfolio
    return corpus


def evidence_corpus(evidence: CandidateEvidenceModel | None) -> dict[str, list[str]]:
    if evidence is None:
        return {"technologies": [], "titles": [], "summaries": [], "raw": []}
    technologies = [t for chunk in evidence.chunks for t in chunk.technologies if t]
    titles = [chunk.title for chunk in evidence.chunks if chunk.title]
    summaries = [chunk.summary for chunk in evidence.chunks if chunk.summary]
    raw = []
    for chunk in evidence.chunks:
        for key, value in chunk.raw.items():
            if isinstance(value, str) and value:
                raw.append(value)
    return {"technologies": technologies, "titles": titles, "summaries": summaries, "raw": raw}


def _hits_in_scope(term: str, scope: Iterable[str]) -> list[str]:
    return [fragment for fragment in scope if fragment and _term_found(fragment, term)]


def classify_skill(
    skill: str,
    candidate: Candidate | None = None,
    evidence: CandidateEvidenceModel | None = None,
) -> SkillAssessment:
    """Classify a JD requirement against candidate + external evidence."""
    skill = canonical_keyword(skill)
    if not skill:
        return SkillAssessment(skill, NO_EXPERIENCE, "empty skill name")

    corpus = candidate_corpus(candidate)
    ext = evidence_corpus(evidence)
    strong = STRONG_ALIASES.get(skill.lower(), [skill])
    related = RELATED_TERMS.get(skill.lower(), [])

    all_prose = "\n".join(
        [*corpus["experience"], *corpus["projects"], *corpus["achievements"]]
    ).lower()
    all_education = "\n".join(corpus["education"]).lower()
    skills_text = " ".join(corpus["skills"]).lower()
    ext_text = " ".join([*ext["technologies"], *ext["titles"], *ext["summaries"], *ext["raw"]]).lower()

    hits: list[str] = []
    probe_terms = [*strong, *related]
    for term in probe_terms:
        hits.extend(f"skills:{hit}" for hit in _hits_in_scope(term, corpus["skills"]))
        hits.extend(f"experience:{hit}" for hit in _hits_in_scope(term, corpus["experience"]))
        hits.extend(f"project:{hit}" for hit in _hits_in_scope(term, corpus["projects"]))
        hits.extend(f"education:{hit}" for hit in _hits_in_scope(term, corpus["education"]))
        hits.extend(
            f"evidence:{hit}"
            for hit in _hits_in_scope(term, [*ext["technologies"], *ext["titles"], *ext["summaries"]])
        )
    hits = list(dict.fromkeys(hits))

    strong_in_skills = any(_term_found(skills_text, t) for t in strong)
    strong_in_prose = any(_term_found(all_prose, t) for t in strong)
    strong_in_education = any(_term_found(all_education, t) for t in strong)
    strong_in_evidence = any(_term_found(ext_text, t) for t in strong)
    related_in_education = any(_term_found(all_education, t) for t in related)
    related_found = any(
        _term_found(f"{all_prose} {all_education} {skills_text} {ext_text}", t) for t in related
    )

    # Learning intent only counts when the skill and a learning keyword share
    # the same sentence; a "learning" keyword elsewhere must not leak.
    sentences = re.split(r"(?<=[.!?])\s+|\n", f"{all_prose} {all_education}")
    sentences = [s for s in sentences if s.strip()]

    def _learning_sentence(terms: list[str]) -> bool:
        return any(
            any(_term_found(sentence, t) for t in terms)
            and any(kw in sentence for kw in LEARNING_KEYWORDS)
            for sentence in sentences
        )

    learning_strong = _learning_sentence(strong)
    learning_related = _learning_sentence(related)

    hit_summary = hits[:4]
    if strong_in_skills or strong_in_evidence:
        if strong_in_evidence and not strong_in_skills:
            return SkillAssessment(skill, CONFIRMED_EXPERIENCE, "corroborated by verified external evidence (e.g. GitHub projects)", hit_summary)
        return SkillAssessment(skill, CONFIRMED_EXPERIENCE, "listed as a skill or directly present in the profile", hit_summary)
    if strong_in_prose:
        if learning_strong:
            return SkillAssessment(skill, LEARNING_INTEREST, "mentioned alongside learning or training intent", hit_summary)
        return SkillAssessment(skill, CONFIRMED_EXPERIENCE, "used directly in experience or project content", hit_summary)
    if strong_in_education or related_in_education:
        if learning_strong:
            return SkillAssessment(skill, LEARNING_INTEREST, "mentioned alongside learning or training intent", hit_summary)
        return SkillAssessment(skill, COURSEWORK_ONLY, "appears only in education or coursework context", hit_summary)
    if related_found:
        if learning_related:
            return SkillAssessment(skill, LEARNING_INTEREST, "mentioned alongside learning or training intent", hit_summary)
        return SkillAssessment(skill, BASIC_KNOWLEDGE, "related evidence found but the skill itself is not confirmed", hit_summary)
    return SkillAssessment(skill, NO_EXPERIENCE, "no supporting evidence found in the profile or external sources", [])


def _question_text(assessment: SkillAssessment) -> str:
    skill = assessment.skill
    if assessment.classification == COURSEWORK_ONLY:
        return (
            f"The job description requires experience with {skill}. Your profile only shows "
            f"{skill} in coursework or training. Have you applied {skill} in any real project, "
            f"internship, or hands-on task since then?"
        )
    if assessment.classification == BASIC_KNOWLEDGE:
        return (
            f"The job description requires experience with {skill}. Your profile suggests related "
            f"but unconfirmed exposure. Can you point to a concrete project, lab, or task where "
            f"you actually used {skill}?"
        )
    if assessment.classification == LEARNING_INTEREST:
        return (
            f"The job description requires experience with {skill}. Your profile shows interest in "
            f"learning {skill} but no completed project. Do you have hands-on exposure to {skill}, "
            f"and should it be listed as in-progress experience?"
        )
    return (
        f"The job description requires experience with {skill}. Based on your profile, {skill} is "
        f"unlisted. Have you ever worked with {skill} or used it in any projects, labs, or coursework?"
    )


def _iter_report_questions(report: ATSReport | dict | None) -> list[Any]:
    return _raw_report_questions(report)


def _coerce_question(raw: Any, required_skills: list[str]) -> InquiryQuestion | None:
    """Normalize one LLM-returned item (str/dict/model) into an InquiryQuestion."""
    if isinstance(raw, InquiryQuestion):
        return raw
    if isinstance(raw, dict):
        keyword = canonical_keyword(str(raw.get("keyword") or raw.get("skill") or ""))
        question = str(raw.get("question") or raw.get("text") or "").strip()
        if keyword and question:
            return InquiryQuestion(keyword=keyword, question=question)
        return None
    if isinstance(raw, str) and raw.strip():
        question = raw.strip()
        for skill in required_skills:
            if skill and skill.lower() in question.lower():
                return InquiryQuestion(keyword=canonical_keyword(skill), question=question)
        return None
    return None


def build_inquiry_questions(
    candidate: Candidate | dict | None,
    job_analysis: JobAnalysis | dict | None,
    report: ATSReport | dict | None = None,
    evidence: CandidateEvidenceModel | dict | None = None,
) -> list[InquiryQuestion]:
    """Return typed, deduplicated interview questions.

    1. Preserves any questions the ATS LLM already produced (converting strings
       into the typed ``{keyword, question}`` shape).
    2. Appends deterministic questions for every JD requirement that the
       candidate has not confirmed, classified into five levels.
    """
    cand = _as_candidate(candidate)
    jd = _as_job_analysis(job_analysis)
    ev = _as_evidence(evidence)

    required_skills = []
    if jd is not None:
        required_skills = [
            canonical_keyword(str(s))
            for s in [*jd.required_skills, *jd.technical_stack]
            if canonical_keyword(str(s)) and len(canonical_keyword(str(s))) > 1
        ]
        preferred = [
            canonical_keyword(str(s))
            for s in jd.preferred_skills
            if canonical_keyword(str(s)) and len(canonical_keyword(str(s))) > 1
        ]
    else:
        preferred = []

    questions: list[InquiryQuestion] = []
    seen: set[str] = set()

    for raw in _iter_report_questions(report):
        question = _coerce_question(raw, required_skills)
        if question and question.keyword.lower() not in seen:
            questions.append(question)
            seen.add(question.keyword.lower())

    for skill in [*required_skills, *preferred]:
        if skill.lower() in seen:
            continue
        assessment = classify_skill(skill, cand, ev)
        if assessment.classification == CONFIRMED_EXPERIENCE:
            # No need to interview the candidate about skills they already hold.
            continue
        questions.append(InquiryQuestion(keyword=skill, question=_question_text(assessment)))
        seen.add(skill.lower())

    return questions


def classification_summary(
    candidate: Candidate | dict | None,
    job_analysis: JobAnalysis | dict | None,
    evidence: CandidateEvidenceModel | dict | None = None,
) -> list[dict[str, str]]:
    """Deterministic per-skill classification used by reports and tests."""
    jd = _as_job_analysis(job_analysis)
    cand = _as_candidate(candidate)
    ev = _as_evidence(evidence)
    skills = []
    if jd is not None:
        skills = [
            canonical_keyword(str(s))
            for s in [*jd.required_skills, *jd.technical_stack, *jd.preferred_skills]
            if canonical_keyword(str(s))
        ]
    result = []
    for skill in list(dict.fromkeys(skills)):
        assessment = classify_skill(skill, cand, ev)
        result.append(
            {
                "skill": skill,
                "classification": assessment.classification,
                "reasoning": assessment.reasoning,
                "evidence": "; ".join(assessment.evidence_hits),
            }
        )
    return result
