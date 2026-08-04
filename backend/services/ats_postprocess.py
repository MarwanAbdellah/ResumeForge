"""Deterministic ATS-report post-processing.

Reconciles the LLM-produced report with the deterministic tailoring plan so the
candidate never sees duplicate questions ("Power BI" and "Familiarity with Power
BI") or suggestions that tell them to claim unverified experience.
"""

from models.pipeline import CandidateEvidenceModel
from models.schemas import ATSReport, Candidate, JobAnalysis

from .gap_service import build_inquiry_questions
from .tailoring import TailoringPlan, _candidate_prose, build_tailoring_plan


def build_grounded_suggestions(
    plan: TailoringPlan,
    candidate: Candidate | None = None,
) -> list[str]:
    """Grounded missing-skill suggestions derived from the tailoring plan.

    - needs_confirmation skills have related evidence (e.g. dashboarding) but
      the exact skill (e.g. Power BI) is unlisted -> ask for a concrete example.
    - must_not_claim-only skills have no signal at all -> mention the gap.
    Never suggests adding something the candidate already has.
    """
    prose = _candidate_prose(candidate).lower() if candidate is not None else ""
    suggestions: list[str] = []

    for skill in plan.needs_confirmation:
        if skill.lower() in prose:
            continue
        suggestions.append(
            f"The job mentions {skill}. Your profile shows related experience, but {skill} "
            f"itself is unlisted. If you genuinely have {skill} experience, add a specific, "
            f"concrete {skill} example — do not claim it otherwise."
        )

    needs = set(plan.needs_confirmation)
    for skill in plan.must_not_claim:
        if skill.lower() in prose or skill in needs:
            continue
        suggestions.append(
            f"The job requires {skill}, which is not present in your profile. If you have used "
            f"{skill} in coursework, labs, or side projects, add a concrete example."
        )

    return list(dict.fromkeys(suggestions))


def _filter_llm_suggestions(suggestions: list[str], plan: TailoringPlan) -> list[str]:
    """Drop LLM suggestions that tell the candidate to claim unsupported skills."""
    prose_plan_terms = {term.lower() for term in plan.must_not_claim}
    kept: list[str] = []
    for suggestion in suggestions:
        lowered = suggestion.lower()
        if any(
            word in lowered
            for word in ("explicitly mention", "claim", "add experience", "list experience")
        ) and any(term in lowered for term in prose_plan_terms):
            # e.g. "Explicitly mention Power BI or Tableau experience if applicable"
            continue
        kept.append(suggestion)
    return list(dict.fromkeys(kept))


def postprocess_ats_report(
    report: ATSReport,
    candidate: Candidate | None,
    analysis: JobAnalysis | None,
    evidence: CandidateEvidenceModel | None = None,
) -> ATSReport:
    """Return a reconciled ATS report with typed questions and grounded suggestions."""
    plan = (
        build_tailoring_plan(candidate, analysis, evidence=evidence)
        if candidate is not None and analysis is not None
        else TailoringPlan()
    )
    questions = build_inquiry_questions(candidate, analysis, report, evidence)
    suggestions = _filter_llm_suggestions(list(report.suggestions or []), plan)
    suggestions.extend(build_grounded_suggestions(plan, candidate))
    return report.model_copy(
        update={
            "inquiry_questions": questions,
            "suggestions": list(dict.fromkeys(suggestions)),
        }
    )
