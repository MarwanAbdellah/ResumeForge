from models.schemas import Candidate, Experience
from renderers import render_resume


def test_resume_renderer_uses_validated_data_only():
    tex = render_resume(Candidate(
        name="Ada Lovelace",
        email="ada@example.com",
        experience=[Experience(title="Engineer", company="Analytical Engines", bullets=["Built 100% safe code & tests."])],
    ))
    assert "Ada Lovelace" in tex
    assert r"100\% safe code \& tests." in tex
    assert "Marwan" not in tex
