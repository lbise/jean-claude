from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jean_claude.errors import ToolError
from jean_claude.tools.base import Tool, ToolContext, ToolResult


@dataclass(slots=True)
class ToolCall:
    tool: str
    args: dict[str, Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.id] = tool

    def get(self, tool_id: str) -> Tool | None:
        return self._tools.get(tool_id)

    def list_tools(self) -> list[Tool]:
        return [self._tools[key] for key in sorted(self._tools.keys())]

    def invoke(self, call: ToolCall, *, context: ToolContext) -> ToolResult:
        tool = self.get(call.tool)
        if tool is None:
            raise ToolError(f"Unknown tool: {call.tool}")
        if not isinstance(call.args, dict):
            raise ToolError(f"Tool call args must be an object for tool: {call.tool}")
        return tool.run(call.args, context)
