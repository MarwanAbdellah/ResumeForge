"""Deterministic projection of verified external evidence into resume projects.

Turns GitHub/Kaggle evidence chunks into concrete, verifiable project entries
that the generator can cite (name + repository URL + README-derived bullets +
optional demo link such as a Tableau dashboard), and guarantees the most
relevant verified projects survive generation even if the LLM omits them.
"""

import re

from models.pipeline import ATSKeywordModel, CandidateEvidenceModel, ExternalProjectModel
from models.pipeline import ResumeModel

DASHBOARD_HOSTS = ("public.tableau.com", "tableau.com", "powerbi.com", "lookerstudio")


def _first_sentences(text: str, max_bullets: int = 2, max_len: int = 180) -> list[str]:
    cleaned = re.sub(r"\s+", " ", (text or "")).strip(" .")
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
    bullets = []
    for sentence in sentences:
        if len(bullets) >= max_bullets:
            break
        if not sentence or len(sentence) < 15:
            continue
        bullets.append(sentence[:max_len].rstrip(" .") + ".")
    return bullets


def _find_demo_url(related_links: list[str], fallback: str | None = None) -> str | None:
    for url in related_links or []:
        lowered = url.lower()
        if any(host in lowered for host in DASHBOARD_HOSTS):
            return url
    return fallback or (related_links[0] if related_links else None)


def _relevance_terms(keywords: ATSKeywordModel | None) -> set[str]:
    if keywords is None:
        return set()
    terms: set[str] = set()
    for group in (
        keywords.required_keywords,
        keywords.preferred_keywords,
        keywords.technical_terms,
        keywords.role_terms,
    ):
        terms.update(term.strip().lower() for term in group if term and term.strip())
    return terms


def build_external_projects(
    evidence: CandidateEvidenceModel | None,
    keywords: ATSKeywordModel | None = None,
    limit: int = 10,
) -> list[ExternalProjectModel]:
    """Build verified project entries from evidence chunks, most relevant first."""
    if evidence is None:
        return []
    terms = _relevance_terms(keywords)

    projects: list[ExternalProjectModel] = []
    seen: set[str] = set()

    for chunk in evidence.chunks:
        if not chunk.title:
            continue
        raw = chunk.raw or {}
        name = chunk.title.strip()
        key = name.lower()
        if key in seen:
            continue

        related_links = raw.get("related_links") or []
        demo_url = _find_demo_url(related_links)
        description = (chunk.summary or "")[:300]
        bullets = _first_sentences(chunk.summary)
        technologies = list(dict.fromkeys(chunk.technologies or []))
        if technologies and len(bullets) < 2:
            bullets.append(f"Tech: {', '.join(technologies[:6])}.")

        haystack = f"{name} {chunk.summary} {' '.join(technologies)}".lower()
        relevance = float(sum(1 for term in terms if term in haystack))

        projects.append(
            ExternalProjectModel(
                name=name,
                url=chunk.url or "",
                description=description,
                bullets=bullets,
                technologies=technologies,
                demo_url=demo_url,
                relevance_score=relevance,
                source=chunk.platform or chunk.source,
            )
        )
        seen.add(key)

    projects.sort(key=lambda project: project.relevance_score, reverse=True)
    return projects[:limit]


def _project_present(resume: ResumeModel, project: ExternalProjectModel) -> bool:
    names = {p.name.strip().lower() for p in resume.projects if p.name}
    urls = {p.url.strip().lower() for p in resume.projects if p.url}
    return (
        project.name.strip().lower() in names
        or bool(project.url and project.url.strip().lower() in urls)
    )


def ensure_evidence_projects(
    resume: ResumeModel,
    projects: list[ExternalProjectModel],
    top_n: int = 2,
) -> ResumeModel:
    """Insert the most relevant verified projects the generator omitted.

    Already-present projects are kept (and their repository/demo links patched
    from verified evidence), while missing relevant projects are prepended so a
    job-relevant project is never lost.
    """
    if not projects:
        return resume

    resume.projects = list(resume.projects)
    by_name = {p.name.strip().lower(): p for p in resume.projects if p.name}

    inserted = 0
    for project in projects:
        existing = by_name.get(project.name.strip().lower())
        if existing is not None:
            existing.url = project.url or existing.url
            existing.demo_url = project.demo_url or existing.demo_url
            if not existing.description and project.description:
                existing.description = project.description
            continue
        if inserted >= top_n:
            break
        resume.projects.insert(0, _to_project(project))
        inserted += 1
    return resume


def _to_project(project: ExternalProjectModel):
    from models.schemas import Project

    return Project(
        name=project.name,
        url=project.url,
        demo_url=project.demo_url,
        description=project.description,
        bullets=project.bullets,
        platform=project.source,
    )
