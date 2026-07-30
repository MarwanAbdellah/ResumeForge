import os
import json
import requests
from typing import Any

from crewai.llms.base_llm import BaseLLM


class NvidiaNimLLM(BaseLLM):
    """
    Custom LLM that calls NVIDIA NIM API directly via requests,
    bypassing litellm entirely. Supports diffusiongemma and other
    NIM models that require chat_template_kwargs.
    """

    llm_type: str = "nvidia_nim"
    model: str = "nvidia-nim/diffusiongemma"
    nim_model: str = "google/diffusiongemma-26b-a4b-it"
    nim_base_url: str = "https://integrate.api.nvidia.com/v1/chat/completions"
    nim_temperature: float = 1.0
    nim_top_p: float = 0.95
    nim_enable_thinking: bool = True
    nim_timeout: int = 120
    is_litellm: bool = False
    provider: str = "nvidia_nim"

    def call(
        self,
        messages: str | list[dict],
        tools: list[dict] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ) -> str:
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        formatted = []
        for m in messages:
            if isinstance(m, dict):
                formatted.append({
                    "role": m.get("role", "user"),
                    "content": m.get("content", ""),
                })
            else:
                formatted.append({"role": "user", "content": str(m)})

        api_key = self.api_key or os.getenv("NVIDIA_NIM_API_KEY", "")

        payload = {
            "messages": formatted,
            "model": self.nim_model,
            "chat_template_kwargs": {"enable_thinking": self.nim_enable_thinking},
            "max_tokens": self.max_tokens or 4096,
            "stream": False,
            "temperature": self.nim_temperature,
            "top_p": self.nim_top_p,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        import time
        max_retries = 3
        last_err = None

        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(
                    self.nim_base_url,
                    headers=headers,
                    json=payload,
                    timeout=self.nim_timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return content

            except requests.exceptions.Timeout:
                last_err = f"NVIDIA NIM API timed out after {self.nim_timeout}s."
            except requests.exceptions.HTTPError as e:
                last_err = f"NVIDIA NIM API HTTP error: {e}\nResponse: {resp.text[:500]}"
            except (KeyError, IndexError) as e:
                last_err = f"Unexpected API response format: {e}\nResponse: {json.dumps(data)[:500]}"
            except Exception as e:
                last_err = f"NVIDIA NIM API connection failed: {e}"

            if attempt < max_retries:
                time.sleep( attempt * 2 )

        raise RuntimeError(f"NVIDIA NIM API call failed after {max_retries} attempts. Last error: {last_err}")

    def supports_function_calling(self) -> bool:
        return False

    def supports_stop_words(self) -> bool:
        return True

    def get_context_window_size(self) -> int:
        return 32000
