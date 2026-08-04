import os
import shutil

import pytest

from models.schemas import Candidate, Experience, Project
from renderers.latex import _latex, _latex_url, render_resume
from services.document_service import DocumentService


PDFLATEX_AVAILABLE = bool(shutil.which("pdflatex") or os.getenv("PDFLATEX_PATH") or shutil.which("lualatex"))


def test_latex_escape():
    escaped = _latex("100% & $50 #1_item {test} ~ ^ < > |")
    assert r"\%" in escaped
    assert r"\&" in escaped
    assert r"\$" in escaped
    assert r"\#" in escaped
    assert r"\_" in escaped
    assert r"\{" in escaped
    assert r"\}" in escaped
    assert "--" in _latex("training – inference — deployment")
    assert r"\textasciitilde{}" in escaped
    assert r"\textasciicircum{}" in escaped
    assert r"\textless{}" in escaped
    assert r"\textgreater{}" in escaped
    assert r"\textbar{}" in escaped


def test_latex_normalizes_zero_width_and_typographic_chars():
    # RTL/LTR marks and control characters must never reach the compiler.
    assert "\u200f" not in _latex("x\u200fy")
    assert "\u200b" not in _latex("a\u200bb")
    assert "..." in _latex("to be continued\u2026")
    assert "-" in _latex("bullet\u2022sep")
    assert "'" in _latex("it\u2019s")
    assert '"' in _latex("\u201cquoted\u201d")


def test_latex_collapses_newlines_in_prose():
    # A blank line inside a macro argument would be a \par and crash LaTeX.
    collapsed = _latex("Support for English \u2194 Arabic\nwith a second line\n\nand a blank line")
    assert "\n" not in collapsed
    assert "Arabic" in collapsed
    assert collapsed == collapsed.strip()
    # The \u2194 arrow maps to <-> and the angle brackets are escaped safely.
    assert r"\textless{}" in collapsed
    assert r"\textgreater{}" in collapsed


def test_empty_bullets_do_not_emit_empty_itemize():
    tex = render_resume(Candidate(
        name="Test User",
        experience=[Experience(title="Engineer", bullets=["", "  "])],
        projects=[Project(name="Project", bullets=[])],
    ))
    # Bullet-level itemize must not be used when there are no bullets: the
    # macros appear exactly once (their definitions), never in the body.
    assert tex.count("\\resumeItemListStart") == 1
    assert tex.count("\\resumeItemListEnd") == 1


def test_latex_url_escape():
    assert r"\&" in _latex_url("https://example.com/a_b?x=1&y=2")
    assert r"\_" in _latex_url("https://example.com/a_b")
    # The percent introduced by encoding must itself be escaped for \href.
    assert r"\%7E" in _latex_url("https://example.com/~user")
    assert r"\%5E" in _latex_url("https://example.com/a^b")


@pytest.mark.skipif(not PDFLATEX_AVAILABLE, reason="LaTeX compiler not installed")
def test_latex_compilation_with_adversarial_text(tmp_path):
    candidate = Candidate(
        name="Test User",
        email="t@example.com",
        summary="R^2 results <5% with ~tilde, A|B, and an ellipsis\u2026",
        experience=[
            Experience(
                title="Engineer",
                bullets=[
                    "m^2 units and 100% accuracy",
                    "x~y with <tag> and 50/50 split",
                    "R\u200f marks and \u201cquotes\u201d",
                    "Support for English \u2194 Arabic\nwith a second line\n\nand a blank line",
                ],
            )
        ],
        projects=[
            Project(
                name="Livekit EN-AR Voice Agent",
                url="https://example.com/~user/a_b?x=1&y=2",
                description="Livekit EN-AR Voice Agent\n- Support for English \u2194 Arabic int",
                bullets=["First bullet", "Second bullet"],
            )
        ],
    )
    pdf_path = DocumentService(tmp_path).compile(render_resume(candidate), "adversarial_cv")
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


@pytest.mark.skipif(not PDFLATEX_AVAILABLE, reason="LaTeX compiler not installed")
def test_latex_compilation_end_to_end(tmp_path):
    candidate = Candidate(
        name="Test User",
        email="test@example.com",
        summary="Python Developer",
        experience=[Experience(title="Engineer", company="Acme", bullets=["Built services."])],
    )
    pdf_path = DocumentService(tmp_path).compile(render_resume(candidate), "test_latex_cv")
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
