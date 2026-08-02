"""Declarative CrewAI agent factory."""

from pathlib import Path
import yaml


AGENTS_CONFIG = Path(__file__).parent.parent / "config" / "agents.yaml"


def load_agent_config() -> dict:
    with AGENTS_CONFIG.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}

