import importlib
from unittest.mock import MagicMock

import pytest

from services.ai_service import AIService, GENERATION_TASKS


def test_generation_tasks_are_routed_to_the_stronger_model():
    fast = MagicMock()
    strong = MagicMock()
    ai = AIService(llm=fast, llm_generation=strong)

    assert ai._route("structure_resume")[0] is fast
    assert ai._route("analyze_job")[0] is fast
    assert ai._route("extract_ats_keywords")[0] is fast
    assert ai._route("review_ats")[0] is fast
    assert ai._route("generate_resume")[0] is strong
    assert ai._route("generate_cover_letter")[0] is strong


def test_generation_tasks_constant_contains_expected_tasks():
    assert "generate_resume" in GENERATION_TASKS
    assert "generate_cover_letter" in GENERATION_TASKS


def test_route_returns_config_model_for_generation():
    from config.settings import settings

    ai = AIService(llm=MagicMock(), llm_generation=MagicMock())
    _, model, _ = ai._route("generate_resume")
    assert model == settings.llm_generation_model
    _, fast_model, _ = ai._route("analyze_job")
    assert fast_model == settings.llm_model
