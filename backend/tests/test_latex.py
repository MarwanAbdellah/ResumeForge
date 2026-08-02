import os
import shutil

import pytest

from models.schemas import Candidate, Experience
from renderers.latex import _latex, _latex_url, render_resume
from services.document_service import DocumentService


PDFLATEX_AVAILABLE = bool(shutil.which("pdflatex") or os.getenv("PDFLATEX_PATH") or shutil.which("lualatex"))


def test_latex_escape():
    escaped = _latex("100% & $50 #1_item {test} ~ ^")
    assert r"\%" in escaped
    assert r"\&" in escaped
    assert r"\$" in escaped
    assert r"\#" in escaped
    assert r"\_" in escaped
    assert r"\{" in escaped
    assert r"\}" in escaped


def test_latex_url_escape():
    assert r"\&" in _latex_url("https://example.com/a_b?x=1&y=2")


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
