"""Deterministic LaTeX rendering from validated domain models."""

import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from models.pipeline import ResumeModel
from models.schemas import Candidate, CoverLetter


TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_environment = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    undefined=StrictUndefined,
    autoescape=False,
    # LaTeX macro arguments like {#1} would collide with Jinja's default
    # {# comment #} delimiters; use a distinctive pair instead.
    comment_start_string="[#",
    comment_end_string="#]",
)


_ZERO_WIDTH = {0x00AD, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0xFEFF, 0x2060}
_TYPOGRAPHIC = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
    "\u2022": "-",
    "\u00b7": "-",
    "\u2044": "/",
    "\u2190": "<-",
    "\u2191": "^",
    "\u2192": "->",
    "\u2194": "<->",
    "\u21d2": "=>",
    "\u00d7": "x",
}


def _normalize_text(value) -> str:
    """Strip control/zero-width/bidi marks, normalize typographic chars, and
    collapse newlines/whitespace so a blank line can never become a ``\\par``
    inside a LaTeX macro argument (e.g. ``\\textit`` / ``\\resumeItem``)."""
    text = str(value or "")
    text = "".join(
        char for char in text if ord(char) not in _ZERO_WIDTH and (char.isprintable() or char in "\n\t")
    )
    for source, replacement in _TYPOGRAPHIC.items():
        text = text.replace(source, replacement)
    return re.sub(r"\s+", " ", text).strip()


def _latex(value) -> str:
    text = _normalize_text(value)
    text = text.replace("\u2013", "--").replace("\u2014", "---").replace("\u2011", "-")
    replacements = (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("^", r"\textasciicircum{}"),
        ("~", r"\textasciitilde{}"),
        ("<", r"\textless{}"),
        (">", r"\textgreater{}"),
        ("|", r"\textbar{}"),
    )
    for source, replacement in replacements:
        text = text.replace(source, replacement)
    return text


def _latex_url(value) -> str:
    text = _normalize_text(value)
    # Percent-encode first so the inserted "%" is escaped as "\%" below
    # (a bare "%" inside \href would start a LaTeX comment).
    for source, replacement in (("~", "%7E"), ("^", "%5E")):
        text = text.replace(source, replacement)
    for source, replacement in (
        ("%", r"\%"),
        ("&", r"\&"),
        ("#", r"\#"),
        ("_", r"\_"),
    ):
        text = text.replace(source, replacement)
    return text


_environment.filters["latex"] = _latex
_environment.filters["latex_url"] = _latex_url

# Skill category -> human-friendly group label. Ordering matters: first match wins.
SKILL_CATEGORY_GROUPS = (
    ("lang", "Programming & Data"),
    ("program", "Programming & Data"),
    ("code", "Programming & Data"),
    ("data", "Data & Analytics"),
    ("analytics", "Data & Analytics"),
    ("analysis", "Data & Analytics"),
    ("machine", "ML & AI"),
    ("deep", "ML & AI"),
    ("agent", "GenAI & Agents"),
    ("genai", "GenAI & Agents"),
    ("llm", "GenAI & Agents"),
    ("ai", "ML & AI"),
    ("ml", "ML & AI"),
    ("cloud", "Cloud & Tools"),
    ("tool", "Cloud & Tools"),
    ("devops", "Cloud & Tools"),
    ("deploy", "Cloud & Tools"),
    ("infra", "Cloud & Tools"),
    ("product", "Productivity"),
    ("soft", "Productivity"),
    ("other", "Productivity"),
)


def _skill_group(category: str) -> str:
    lowered = (category or "").strip().lower()
    if not lowered:
        return "Tools"
    for marker, group in SKILL_CATEGORY_GROUPS:
        if marker in lowered:
            return group
    return "Tools"


def build_skill_groups(skills: list[dict]) -> list[dict]:
    """Group skills by friendly category, preserving JD-relevance order.

    Group order follows the first appearance of each group in the (LLM-ordered)
    skill list; skills within a group keep their order and duplicates are dropped.
    """
    groups: dict[str, list[str]] = {}
    first_seen: dict[str, int] = {}
    for index, skill in enumerate(skills):
        name = str(skill.get("name") or "").strip()
        if not name:
            continue
        group = _skill_group(str(skill.get("category") or ""))
        if name not in groups.setdefault(group, []):
            groups[group].append(name)
        first_seen.setdefault(group, index)
    ordered_groups = sorted(groups, key=lambda g: first_seen[g])
    return [{"name": group, "skills": groups[group]} for group in ordered_groups]


def _resume_data(
    resume: ResumeModel,
    candidate: Candidate | None = None,
    fallback_headline: str = "",
) -> dict:
    data = resume.model_dump(mode="json")
    data["skill_groups"] = build_skill_groups(data.get("skills", []))
    if candidate is None:
        _remove_blank_bullets(data)
        return data

    source = candidate.model_dump(mode="json")
    # Identity is factual candidate data, never LLM-generated presentation data.
    for field in ("name", "email", "phone", "location"):
        data[field] = source.get(field, "")
    data["links"] = source.get("links", {})
    if not data.get("headline"):
        data["headline"] = fallback_headline

    summary = data.get("summary", "")
    if "Distinct from CandidateModel" in summary or summary.startswith("An optimized, ATS-ready resume"):
        data["summary"] = source.get("summary", "")
    _remove_blank_bullets(data)
    return data


def _remove_blank_bullets(data: dict) -> None:
    """Prevent empty LaTeX list environments from reaching the compiler."""
    for section in ("experience", "projects"):
        for item in data.get(section, []):
            item["bullets"] = [
                bullet for bullet in item.get("bullets", []) if str(bullet).strip()
            ]


def render_resume(
    candidate: Candidate | ResumeModel,
    source_candidate: Candidate | None = None,
    fallback_headline: str = "",
) -> str:
    """Render resume content with canonical identity from the source candidate."""
    if isinstance(candidate, ResumeModel):
        data = _resume_data(candidate, source_candidate, fallback_headline)
    else:
        data = candidate.model_dump(mode="json")
        data["skill_groups"] = build_skill_groups(data.get("skills", []))
        _remove_blank_bullets(data)
    return _environment.get_template("resume.tex.j2").render(candidate=data)


def render_cover_letter(letter: CoverLetter, candidate: Candidate | ResumeModel) -> str:
    return _environment.get_template("cover_letter.tex.j2").render(
        letter=letter.model_dump(mode="json"), candidate=candidate.model_dump(mode="json")
    )
