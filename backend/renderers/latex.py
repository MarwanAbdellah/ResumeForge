"""Deterministic LaTeX rendering from validated domain models."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from models.schemas import Candidate, CoverLetter


TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_environment = Environment(loader=FileSystemLoader(TEMPLATE_DIR), undefined=StrictUndefined, autoescape=False)


def _latex(value) -> str:
    text = str(value or "")
    replacements = (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"))
    for source, replacement in replacements:
        text = text.replace(source, replacement)
    return text


def _latex_url(value) -> str:
    text = str(value or "")
    for source, replacement in (("%", r"\%"), ("&", r"\&"), ("#", r"\#"), ("_", r"\_")):
        text = text.replace(source, replacement)
    return text


_environment.filters["latex"] = _latex
_environment.filters["latex_url"] = _latex_url


def render_resume(candidate: Candidate) -> str:
    return _environment.get_template("resume.tex.j2").render(candidate=candidate.model_dump(mode="json"))


def render_cover_letter(letter: CoverLetter, candidate: Candidate) -> str:
    return _environment.get_template("cover_letter.tex.j2").render(
        letter=letter.model_dump(mode="json"), candidate=candidate.model_dump(mode="json")
    )
