from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ToolContext:
    session_id: str | None = None


@dataclass(slots=True)
class ToolResult:
    tool: str
    ok: bool
    output: str
    exit_code: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(Protocol):
    id: str
    name: str
    description: str
    input_schema: dict[str, Any]

    def run(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        ...
