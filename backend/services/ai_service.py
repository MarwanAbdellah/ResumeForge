"""The single CrewAI execution and validation boundary."""

import asyncio
import os
from typing import Any

from crewai import Crew, LLM, Process

from config.settings import settings
from crew.crew import ResumeForgeCrew
from observability.events import emit_event, stage_span
from observability.metrics import metrics

# Tasks that must produce genuinely tailored prose run on the stronger model.
GENERATION_TASKS = frozenset({"generate_resume", "generate_cover_letter"})


def _configure_provider_key(model: str, api_key: str | None) -> None:
    if not api_key:
        return
    provider_env = {
        "openrouter/": "OPENROUTER_API_KEY",
        "nvidia_nim/": "NVIDIA_NIM_API_KEY",
        "openai/": "OPENAI_API_KEY",
        "anthropic/": "ANTHROPIC_API_KEY",
        "groq/": "GROQ_API_KEY",
    }
    for prefix, env_name in provider_env.items():
        if model.startswith(prefix):
            os.environ[env_name] = api_key
            break


class AIService:
    def __init__(self, llm: LLM | None = None, llm_generation: LLM | None = None):
        self.llm = llm or self._create_llm(settings.llm_model, settings.llm_api_key)
        self.llm_generation = llm_generation or self._create_llm(
            settings.llm_generation_model, settings.llm_generation_api_key
        )
        self._concurrency = asyncio.Semaphore(max(1, settings.llm_max_concurrency))

    @staticmethod
    def _create_llm(model: str, api_key: str | None) -> LLM:
        _configure_provider_key(model, api_key)
        return LLM(
            model=model,
            api_key=api_key,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    @staticmethod
    def _provider(model: str) -> str:
        return model.split("/", 1)[0] if "/" in model else model

    def _route(self, task_name: str) -> tuple[LLM, str, str | None]:
        """Return (llm, model, api_key) for a task name."""
        if task_name in GENERATION_TASKS:
            return (
                self.llm_generation,
                settings.llm_generation_model,
                settings.llm_generation_api_key,
            )
        return self.llm, settings.llm_model, settings.llm_api_key

    @staticmethod
    def _usage(result: Any) -> dict[str, int]:
        usage = getattr(result, "token_usage", None)
        if not isinstance(usage, dict):
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return {
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage.get("total_tokens", 0) or 0),
        }

    @staticmethod
    def _cost(usage: dict[str, int]) -> float:
        return (
            usage["prompt_tokens"] * settings.llm_input_cost_per_1m
            + usage["completion_tokens"] * settings.llm_output_cost_per_1m
        ) / 1_000_000

    async def arun(self, task_name: str, inputs: dict[str, Any]) -> Any:
        """Bounded async adapter for synchronous CrewAI kickoff."""
        async with self._concurrency:
            return await asyncio.to_thread(self.run, task_name, inputs)

    def run(self, task_name: str, inputs: dict[str, Any]) -> Any:
        llm, model, _ = self._route(task_name)
        provider = self._provider(model)
        last_error = None
        for attempt in range(2):
            task = ResumeForgeCrew(llm).isolated_task(task_name)
            try:
                with stage_span(
                    task_name,
                    component="CrewAI",
                    agent=task.agent.role,
                    retry_count=attempt,
                    model=model,
                    provider=provider,
                ):
                    result = Crew(
                        agents=[task.agent],
                        tasks=[task],
                        process=Process.sequential,
                        verbose=False,
                    ).kickoff(inputs=inputs)
                    usage = self._usage(result)
                    emit_event(
                        task_name,
                        "usage",
                        prompt_tokens=usage["prompt_tokens"],
                        completion_tokens=usage["completion_tokens"],
                        total_tokens=usage["total_tokens"],
                        estimated_cost_usd=self._cost(usage),
                        retry_count=attempt,
                        model=model,
                        provider=provider,
                    )
                    if result.pydantic is not None:
                        output_model = ResumeForgeCrew.TASK_OUTPUT_MODELS[task_name]
                        validated = output_model.model_validate(result.pydantic.model_dump())
                        emit_event(
                            task_name,
                            "validated",
                            validation_status="passed",
                            retry_count=attempt,
                            model=model,
                            provider=provider,
                        )
                        metrics.increment("resumeforge_ai_tasks_total", task=task_name, status="success")
                        return validated
                    last_error = ValueError(
                        f"CrewAI task {task_name} did not return structured output"
                    )
            except Exception as exc:
                metrics.increment("resumeforge_ai_tasks_total", task=task_name, status="failed")
                emit_event(
                    task_name,
                    "retry" if attempt == 0 else "failed",
                    retry_count=attempt,
                    error=str(exc),
                    validation_status="repairing" if attempt == 0 else "failed",
                    model=model,
                    provider=provider,
                )
                last_error = exc
        raise ValueError(
            f"Structured task {task_name} failed after repair retry: {last_error}"
        ) from last_error
