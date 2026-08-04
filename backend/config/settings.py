"""Application settings loaded from environment variables."""

import os
from dataclasses import dataclass

DEFAULT_LLM_MODEL = "nvidia_nim/nvidia/nemotron-3-ultra-550b-a55b"
DEFAULT_GENERATION_MODEL = "nvidia_nim/meta/llama-3.3-70b-instruct"

# Defaults are resolved at import time so the frozen dataclass stays simple.
# If the module is imported before ``load_dotenv()`` runs, settings fall back
# to these values; callers (main.py) load the env file before importing.
_LLM_MODEL = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)
_LLM_GENERATION_MODEL = os.getenv("LLM_MODEL_GENERATION") or _LLM_MODEL


def _resolve_api_key(model: str) -> str | None:
    """Pick the provider-specific env var, falling back to the generic key.

    ``LLM_API_KEY`` is a convenience override that works for every provider;
    the provider-specific vars (OPENROUTER_API_KEY, NVIDIA_NIM_API_KEY, ...)
    are preferred when they are set so users never mix providers.
    """
    provider_env = {
        "openrouter/": "OPENROUTER_API_KEY",
        "nvidia_nim/": "NVIDIA_NIM_API_KEY",
        "openai/": "OPENAI_API_KEY",
        "anthropic/": "ANTHROPIC_API_KEY",
        "groq/": "GROQ_API_KEY",
    }
    for prefix, env_name in provider_env.items():
        if model.startswith(prefix):
            return os.getenv(env_name) or os.getenv("LLM_API_KEY")
    return os.getenv("LLM_API_KEY")


_LLM_API_KEY = _resolve_api_key(_LLM_MODEL)
_LLM_GENERATION_API_KEY = _resolve_api_key(_LLM_GENERATION_MODEL)


@dataclass(frozen=True)
class Settings:
    llm_model: str = _LLM_MODEL
    llm_api_key: str | None = _LLM_API_KEY
    llm_generation_model: str = _LLM_GENERATION_MODEL
    llm_generation_api_key: str | None = _LLM_GENERATION_API_KEY
    output_dir: str = os.getenv("OUTPUT_DIR", "output")
    latex_timeout_seconds: int = int(os.getenv("LATEX_TIMEOUT_SECONDS", "60"))
    llm_max_concurrency: int = int(os.getenv("LLM_MAX_CONCURRENCY", "4"))
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))
    llm_input_cost_per_1m: float = float(os.getenv("LLM_INPUT_COST_PER_1M", "0.0"))
    llm_output_cost_per_1m: float = float(os.getenv("LLM_OUTPUT_COST_PER_1M", "0.0"))
    cli_timeline: bool = os.getenv("RF_CLI_TIMELINE", "false").lower() in {"1", "true", "yes"}
    event_buffer_capacity: int = int(os.getenv("RF_EVENT_BUFFER_CAPACITY", "200"))


settings = Settings()
