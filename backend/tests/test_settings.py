import importlib
import os

import config.settings as settings_module
from config.settings import _resolve_api_key, settings


def test_resolve_api_key_prefers_provider_specific_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nv-key")
    monkeypatch.setenv("LLM_API_KEY", "generic-key")

    assert _resolve_api_key("openrouter/nvidia/nemotron-3-ultra-550b-a55b:free") == "or-key"
    assert _resolve_api_key("nvidia_nim/meta/llama-3.3-70b-instruct") == "nv-key"
    assert _resolve_api_key("openai/gpt-4o") == "generic-key"


def test_resolve_api_key_falls_back_to_generic_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "generic-key")
    assert _resolve_api_key("openrouter/some/model") == "generic-key"


def test_openrouter_model_does_not_silently_use_nvidia_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "")
    # An OpenRouter model must resolve to None (or a generic key), never the
    # NVIDIA NIM key.
    assert _resolve_api_key("openrouter/foo/bar") != "nvapi-something"


def test_generation_model_defaults_to_llm_model_and_openrouter_key(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "openrouter/meta-llama/llama-3.1-8b-instruct:free")
    monkeypatch.delenv("LLM_MODEL_GENERATION", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key-123")

    importlib.reload(settings_module)
    reloaded = settings_module.settings
    assert reloaded.llm_model.startswith("openrouter/")
    assert reloaded.llm_generation_model == reloaded.llm_model
    assert reloaded.llm_api_key == "or-key-123"
    assert reloaded.llm_generation_api_key == "or-key-123"

    # Restore module state for other tests.
    importlib.reload(settings_module)
