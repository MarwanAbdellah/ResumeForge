import pytest

crewai = pytest.importorskip("crewai")

from crew.tasks import OUTPUT_MODELS, load_task_config  # noqa: E402


def test_every_configured_task_has_a_typed_output_model():
    config = load_task_config()

    assert set(config) == set(OUTPUT_MODELS)
    assert all(model is not None for model in OUTPUT_MODELS.values())


def test_crewai_class_exposes_explicit_contexts_and_yaml_configuration():
    from crew.crew import ResumeForgeCrew

    instance = ResumeForgeCrew(llm=None)
    assert instance.agents_config
    assert instance.tasks_config
    assert instance.optimize_resume().context
    assert instance.generate_cover_letter().context
    assert instance.review_ats().context
