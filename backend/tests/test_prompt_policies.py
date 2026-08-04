from pathlib import Path

import yaml

from config.prompts import HUMANIZER_GUIDANCE


def test_humanizer_policy_is_local_and_factuality_first():
    assert "invent accomplishments" in HUMANIZER_GUIDANCE.lower()
    assert "technical names" in HUMANIZER_GUIDANCE
    assert "MIT" in HUMANIZER_GUIDANCE


def test_generation_tasks_receive_humanizer_policy_placeholder():
    path = Path(__file__).parents[1] / "config" / "tasks.yaml"
    tasks = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "{humanizer_guidance}" in tasks["generate_resume"]["description"]
    assert "{humanizer_guidance}" in tasks["generate_cover_letter"]["description"]
