"""Deterministic JD-to-candidate tailoring plan and post-generation validation.

The plan is built with Python rules (no LLM) before the generation model is
called, so the generator receives explicit confirmed / needs-confirmation /
must-not-claim lists instead of only prose instructions. The validator checks
the generated resume against those rules afterwards.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from models.pipeline import ATSKeywordModel, CandidateEvidenceModel, ResumeModel
from models.schemas import Candidate, JobAnalysis

from .gap_service import RELATED_TERMS

# Canonical JD phrase -> candidate-relevant skill names.
ALIASES: dict[str, list[str]] = {
    "python pandas": ["Python", "Pandas"],
    "python + pandas": ["Python", "Pandas"],
    "pandas": ["Pandas", "Python"],
    "dashboarding": ["Power BI", "Tableau", "dashboard development"],
    "reporting": ["reporting", "stakeholder reporting", "recurring reports"],
    "data analysis": ["data analysis", "analytics"],
    "data analytics": ["data analysis", "analytics"],
    "power bi": ["Power BI"],
    "pivot tables": ["Excel", "pivot tables"],
    "excel": ["Excel"],
    "sql": ["SQL"],
    "python": ["Python"],
    "machine learning": ["machine learning"],
    "ml": ["machine learning"],
}

# Terms whose presence means a skill was actually used (confirmed).
STRONG_CONTEXT = ("experience", "project", "built", "developed", "shipped",
                  "implemented", "led", "designed", "deployed", "migrated",
                  "automated", "analyzed", "used")


@dataclass
class TailoringPlan:
    confirmed: list[str] = field(default_factory=list)
    verified_external_evidence: list[str] = field(default_factory=list)
    needs_confirmation: list[str] = field(default_factory=list)
    must_not_claim: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        import json
        return json.dumps(
            {
                "confirmed": list(dict.fromkeys(self.confirmed)),
                "verified_external_evidence": list(dict.fromkeys(self.verified_external_evidence)),
                "needs_confirmation": list(dict.fromkeys(self.needs_confirmation)),
                "must_not_claim": list(dict.fromkeys(self.must_not_claim)),
            },
            ensure_ascii=False,
            indent=2,
        )


def _norm(value: str) -> str:
    return " ".join(value.lower().strip().split())


def extract_requirements(
    job_analysis: JobAnalysis | None,
    ats_keywords: ATSKeywordModel | None = None,
) -> list[str]:
    """Canonical JD requirements, deduplicated, order-preserving."""
    requirements: list[str] = []
    if job_analysis is not None:
        requirements.extend(job_analysis.required_skills or [])
        requirements.extend(job_analysis.technical_stack or [])
        requirements.extend(job_analysis.preferred_skills or [])
        requirements.extend(job_analysis.ats_keywords or [])
    if ats_keywords is not None:
        requirements.extend(ats_keywords.required_keywords or [])
        requirements.extend(ats_keywords.technical_terms or [])
        requirements.extend(ats_keywords.role_terms or [])
    return list(dict.fromkeys(str(req).strip() for req in requirements if str(req).strip()))


def normalize_requirements(requirements: list[str]) -> list[str]:
    """Expand aliases into canonical skill names."""
    expanded: list[str] = []
    for req in requirements:
        key = _norm(req)
        if key in ALIASES:
            expanded.extend(ALIASES[key])
        else:
            expanded.append(req.strip())
    return list(dict.fromkeys(expanded))


def _term_in(text: str, term: str) -> bool:
    if not term:
        return False
    needle = re.escape(term.strip().lower())
    pattern = rf"(?<![a-z0-9]){needle}(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def _candidate_prose(candidate: Candidate) -> str:
    parts: list[str] = []
    for exp in candidate.experience:
        parts.append(exp.title or "")
        parts.append(exp.company or "")
        parts.extend(exp.bullets or [])
    for project in candidate.projects:
        parts.append(project.name or "")
        parts.append(project.description or "")
        parts.extend(project.bullets or [])
    parts.extend(a.title for a in candidate.achievements if a.title)
    return " ".join(parts)


def _evidence_text(evidence: CandidateEvidenceModel | None) -> tuple[str, list[str]]:
    if evidence is None:
        return "", []
    parts: list[str] = []
    titles: list[str] = []
    for chunk in evidence.chunks:
        if chunk.title:
            titles.append(chunk.title)
        parts.append(chunk.title or "")
        parts.append(chunk.summary or "")
        parts.extend(chunk.technologies or [])
        for key, value in chunk.raw.items():
            if isinstance(value, str) and value:
                parts.append(value)
    return " ".join(parts), titles


def _candidate_skills(candidate: Candidate) -> list[str]:
    return [s.name for s in candidate.skills if s.name]


def build_tailoring_plan(
    candidate: Candidate,
    job_analysis: JobAnalysis,
    ats_keywords: ATSKeywordModel | None = None,
    evidence: CandidateEvidenceModel | None = None,
) -> TailoringPlan:
    """Classify each canonical requirement as confirmed / external / needs-confirmation / must-not-claim."""
    requirements = normalize_requirements(extract_requirements(job_analysis, ats_keywords))
    prose = _candidate_prose(candidate).lower()
    skills = " ".join(_candidate_skills(candidate)).lower()
    education = " ".join(
        part for entry in candidate.education for part in (entry.field, entry.details, entry.degree) if part
    ).lower()
    evidence_text, evidence_titles = _evidence_text(evidence)

    plan = TailoringPlan()
    for skill in requirements:
        term = skill.strip()
        if not term:
            continue
        in_candidate = _term_in(prose, term) or _term_in(skills, term)
        in_education = _term_in(education, term)
        in_evidence = _term_in(evidence_text, term)
        related = any(
            _term_in(blob, r)
            for r in RELATED_TERMS.get(term.lower(), [])
            for blob in (prose, skills, education, evidence_text)
        )

        if in_candidate:
            plan.confirmed.append(term)
        elif in_evidence:
            plan.verified_external_evidence.append(term)
        elif in_education or related:
            # Weak/related signal: ask the candidate, but never claim it until
            # explicitly confirmed.
            plan.needs_confirmation.append(term)
            plan.must_not_claim.append(term)
        else:
            plan.must_not_claim.append(term)

    # Attach the actual evidence project titles so the generator can cite them.
    plan.verified_external_evidence.extend(
        title for title in evidence_titles if title and not _term_in(prose, title)
    )
    return plan


# ── Post-generation validation ─────────────────────────────────────────────

def token_overlap(generated_text: str, original_text: str) -> float:
    """Coverage of original tokens present in generated text (0..1)."""
    original_tokens = set(re.findall(r"[a-z0-9]+", (original_text or "").lower()))
    generated_tokens = set(re.findall(r"[a-z0-9]+", (generated_text or "").lower()))
    if not original_tokens:
        return 0.0
    return len(original_tokens & generated_tokens) / len(original_tokens)


def _resume_prose(resume: ResumeModel) -> str:
    parts = [resume.summary or ""]
    for exp in resume.experience:
        parts.append(exp.title or "")
        parts.extend(exp.bullets or [])
    for project in resume.projects:
        parts.append(project.name or "")
        parts.append(project.description or "")
        parts.extend(project.bullets or [])
    return " ".join(parts)


def validate_generated_resume(
    resume: ResumeModel,
    candidate: Candidate,
    plan: TailoringPlan,
    evidence: CandidateEvidenceModel | None = None,
) -> dict[str, list[str]]:
    """Return categorized issues; empty lists mean the resume passed."""
    issues: dict[str, list[str]] = {
        "summary_echo": [],
        "projects_prioritized": [],
        "invented_skills": [],
        "keyword_coverage": [],
        "fact_integrity": [],
    }

    # 1. Summary must have changed measurably toward the role.
    if candidate.summary and resume.summary:
        overlap = token_overlap(resume.summary, candidate.summary)
        if overlap >= 0.85 or resume.summary.strip().lower() == candidate.summary.strip().lower():
            issues["summary_echo"].append(
                f"Summary is {round(overlap * 100)}% identical to the input summary; rewrite it for the target role."
            )

    # 2. Supported-skill universe: candidate + evidence + plan-confirmed.
    supported = set(_candidate_skills(candidate))
    supported.update(plan.confirmed)
    supported.update(plan.verified_external_evidence)
    supported.update(plan.needs_confirmation)
    if evidence:
        for chunk in evidence.chunks:
            supported.update(chunk.technologies or [])
            if chunk.title:
                supported.add(chunk.title)
    supported_norm = {_norm(s) for s in supported}
    must_not_norm = {_norm(s) for s in plan.must_not_claim}

    for skill in resume.skills:
        if _norm(skill.name) in must_not_norm:
            issues["invented_skills"].append(
                f"Resume claims '{skill.name}' which is in must_not_claim; remove it."
            )
        elif _norm(skill.name) not in supported_norm:
            issues["invented_skills"].append(
                f"Resume lists unsupported skill '{skill.name}' not present in the candidate, evidence, or tailoring plan."
            )

    # 3. Confirmed keywords should appear naturally in the generated content.
    resume_text = _resume_prose(resume).lower()
    if plan.confirmed:
        present = [term for term in plan.confirmed if _term_in(resume_text, term)]
        if not present:
            issues["keyword_coverage"].append(
                "None of the confirmed JD keywords appear in the generated resume; incorporate them."
            )

    # 4. Evidence-backed projects should be surfaced.
    evidence_visible = plan.verified_external_evidence
    if evidence_visible and resume.projects:
        resume_project_text = " ".join(
            p.name for p in resume.projects if p.name
        ).lower() + " " + _resume_prose(resume).lower()
        surfaced = [item for item in evidence_visible if _term_in(resume_project_text, item)]
        if not surfaced:
            issues["projects_prioritized"].append(
                "Verified external evidence exists but no evidence-backed project is surfaced; prioritize them."
            )

    # 5. Original facts and dates must be unchanged.
    candidate_dates = [exp.dates for exp in candidate.experience if exp.dates]
    resume_dates = [exp.dates for exp in resume.experience if exp.dates]
    if candidate_dates:
        if len(candidate_dates) > len(resume_dates):
            issues["fact_integrity"].append("Some experience date ranges were dropped from the resume.")
        else:
            for original in candidate_dates:
                if original not in resume_dates:
                    issues["fact_integrity"].append(
                        f"Date range '{original}' from the source resume is missing or changed."
                    )
    candidate_urls = [p.url for p in candidate.projects if p.url]
    candidate_urls += [c.url for c in candidate.certifications if c.url]
    resume_blob = resume.model_dump_json().lower()
    for url in candidate_urls:
        if url and url.lower() not in resume_blob:
            issues["fact_integrity"].append(f"URL '{url}' from the source resume was dropped.")

    return issues


def summarize_issues(issues: dict[str, list[str]]) -> str:
    lines = []
    for category, messages in issues.items():
        for message in messages:
            lines.append(f"- {category}: {message}")
    return "\n".join(lines)
