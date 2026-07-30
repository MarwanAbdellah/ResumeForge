import os
from pathlib import Path
import pytest
from crew import _latex_escape, html_to_latex, compile_latex_to_pdf, run_compilation


def test_latex_escape():
    raw = "100% & $50 #1_item {test} ~ ^ \\"
    escaped = _latex_escape(raw)
    assert r"\%" in escaped
    assert r"\&" in escaped
    assert r"\$" in escaped
    assert r"\#" in escaped
    assert r"\_" in escaped
    assert r"\{" in escaped
    assert r"\}" in escaped


def test_html_to_latex_conversion():
    html = """
    <div class="header">
        <h1 class="name">Jane Doe</h1>
        <div class="contact-line">
            <a href="mailto:jane@example.com">jane@example.com</a> |
            <a href="https://github.com/janedoe">GitHub</a>
        </div>
    </div>
    <div class="section">
        <h2 class="title">Experience</h2>
        <div class="entry">
            <span class="job">Software Engineer</span>
            <span class="company">Acme Corp</span>
            <span class="date">2021 - Present</span>
            <ul>
                <li>Built scalable Python services</li>
            </ul>
        </div>
    </div>
    """
    tex = html_to_latex(html, doc_type="cv")
    assert r"\documentclass" in tex
    assert "Jane Doe" in tex
    assert r"\href{mailto:jane@example.com}" in tex
    assert r"\section*{Experience}" in tex
    assert r"\item Built scalable Python services" in tex


def test_latex_compilation_end_to_end(tmp_path):
    html = """
    <div class="header"><h1 class="name">Test User</h1></div>
    <div class="section"><h2 class="title">Summary</h2><p>Python Developer</p></div>
    """
    pdf_path = run_compilation(html, "test_latex_cv")
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
    if pdf_path.exists():
        pdf_path.unlink()
