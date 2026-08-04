"""Reusable deterministic prompt policies."""

from pathlib import Path


HUMANIZER_GUIDANCE = (
    Path(__file__).parent / "prompts" / "humanizer.md"
).read_text(encoding="utf-8")
