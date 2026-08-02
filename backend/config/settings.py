"""Application settings loaded from environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    llm_model: str = os.getenv("LLM_MODEL", "nvidia_nim/nvidia/nemotron-3-ultra-550b-a55b")
    llm_api_key: str | None = os.getenv("LLM_API_KEY") or os.getenv("NVIDIA_NIM_API_KEY")
    output_dir: str = os.getenv("OUTPUT_DIR", "output")
    latex_timeout_seconds: int = int(os.getenv("LATEX_TIMEOUT_SECONDS", "60"))


settings = Settings()
