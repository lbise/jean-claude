from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class LLMResult:
    provider: str
    model: str
    text: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] | None = None


class LLMClient(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> LLMResult:
        ...
