"""Structured CrewAI task execution."""

import os
from typing import Any

from crewai import Crew, LLM, Process

from config.settings import settings
from crew.crew import ResumeForgeCrew
from observability.events import emit_event, stage_span
from observability.metrics import metrics


def _configure_provider_key(model: str, api_key: str | None) -> None:
    if not api_key:
        return
    provider_env = {
        "openrouter/": "OPENROUTER_API_KEY",
        "nvidia_nim/": "NVIDIA_NIM_API_KEY",
        "openai/": "OPENAI_API_KEY",
        "anthropic/": "ANTHROPIC_API_KEY",
    }
    for prefix, env_name in provider_env.items():
        if model.startswith(prefix):
            os.environ[env_name] = api_key
            break


class AIService:
    def __init__(self, llm: LLM | None = None):
        self.llm = llm or self._create_llm()

    @staticmethod
    def _create_llm() -> LLM:
        _configure_provider_key(settings.llm_model, settings.llm_api_key)
        return LLM(model=settings.llm_model, api_key=settings.llm_api_key, temperature=0.2, max_tokens=4096)

    def run(self, task_name: str, inputs: dict[str, Any]) -> Any:
        last_error = None
        for attempt in range(2):
            task = ResumeForgeCrew(self.llm).isolated_task(task_name)
            try:
                with stage_span(task_name, component="CrewAI", agent=task.agent.role, retry_count=attempt):
                    result = Crew(
                        agents=[task.agent],
                        tasks=[task],
                        process=Process.sequential,
                        verbose=False,
                    ).kickoff(inputs=inputs)
                    usage = getattr(result, "token_usage", None)
                    if isinstance(usage, dict):
                        emit_event(task_name, "usage", prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"), total_tokens=usage.get("total_tokens"), retry_count=attempt)
                    if result.pydantic is not None:
                        metrics.increment("resumeforge_ai_tasks_total", task=task_name, status="success")
                        return result.pydantic
                    last_error = ValueError(f"CrewAI task {task_name} did not return structured output")
            except Exception as exc:
                metrics.increment("resumeforge_ai_tasks_total", task=task_name, status="failed")
                emit_event(task_name, "retry" if attempt == 0 else "failed", retry_count=attempt, exception=type(exc).__name__)
                last_error = exc
        raise ValueError(f"Structured task {task_name} failed after repair retry: {last_error}") from last_error
