from models.pipeline import ATSKeywordModel, CandidateEvidenceModel
from models.schemas import Candidate, JobAnalysis
from services.context_builder import GenerationContextBuilder


def test_context_builder_composes_without_mutating_candidate():
    candidate = Candidate(name="Jane", portfolio=[])
    before = candidate.model_dump(mode="json")
    context = GenerationContextBuilder().build(
        candidate,
        JobAnalysis(title="Engineer"),
        ATSKeywordModel(required_keywords=["Python"]),
        CandidateEvidenceModel(),
        "Python engineer",
    )

    assert context.candidate.name == "Jane"
    assert candidate.model_dump(mode="json") == before
    assert context.ats_keywords.required_keywords == ["Python"]
