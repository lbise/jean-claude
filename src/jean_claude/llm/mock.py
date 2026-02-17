from __future__ import annotations

from jean_claude.llm.base import LLMResult


class MockLLMClient:
    provider_name = "mock"
    default_model = "mock-v1"

    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> LLMResult:
        selected_model = model or self.default_model
        prefix = "Mock recommendation"
        if system_prompt:
            prefix = f"{prefix} ({system_prompt[:40]})"
        text = f"{prefix}: based on your input, consider '{prompt[:80]}'."
        return LLMResult(
            provider=self.provider_name,
            model=selected_model,
            text=text,
            usage={"input_tokens": 0, "output_tokens": 0},
            raw={"source": "mock"},
        )
