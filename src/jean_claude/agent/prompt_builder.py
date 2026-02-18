from __future__ import annotations

import json
from typing import Any

from jean_claude.agent.session import ChatMessage
from jean_claude.prompts import FlowDefinition, FlowState, PromptPackRepository, ToolDefinition
from jean_claude.tools import ToolRegistry


class PromptBuilder:
    def __init__(self, repository: PromptPackRepository, tool_registry: ToolRegistry) -> None:
        self.repository = repository
        self.tool_registry = tool_registry

    def build_system_prompt(
        self,
        *,
        flow: FlowDefinition,
        state: FlowState,
        tools: list[ToolDefinition],
        output_schema: dict[str, Any],
    ) -> str:
        parts: list[str] = []

        for relative_path in flow.base_layers:
            parts.append(self.repository.read_text(relative_path))

        parts.append(self.repository.read_text(flow.mode_prompt))
        parts.append(self._tools_section(tools))
        parts.append(self._task_context_section(state.task_context))
        parts.append(self._output_schema_section(output_schema))

        return "\n\n".join(part for part in parts if part.strip())

    def build_user_prompt(
        self,
        *,
        mode: str,
        flow_state: str,
        user_profile: dict[str, Any],
        latest_user_message: str,
        message_history: list[ChatMessage],
    ) -> str:
        history_payload = [{"role": msg.role, "content": msg.content} for msg in message_history]
        flow_context = {
            "mode": mode,
            "flow_state": flow_state,
        }
        return "\n".join(
            [
                "[USER_PROFILE_JSON]",
                json.dumps(user_profile, indent=2, sort_keys=True),
                "[/USER_PROFILE_JSON]",
                "",
                "[FLOW_CONTEXT_JSON]",
                json.dumps(flow_context, indent=2, sort_keys=True),
                "[/FLOW_CONTEXT_JSON]",
                "",
                "[LATEST_USER_MESSAGE]",
                latest_user_message,
                "[/LATEST_USER_MESSAGE]",
                "",
                "[MESSAGE_HISTORY_JSON]",
                json.dumps(history_payload, indent=2, sort_keys=True),
                "[/MESSAGE_HISTORY_JSON]",
            ]
        )

    def _tools_section(self, tools: list[ToolDefinition]) -> str:
        lines = ["# Available Tools"]
        if not tools:
            lines.append("- none")
            return "\n".join(lines)

        for tool in tools:
            lines.append(f"- `{tool.id}`: {tool.name} - {tool.description}")

            registered = self.tool_registry.get(tool.id)
            if registered is not None:
                schema_text = json.dumps(registered.input_schema, indent=2, sort_keys=True)
                lines.append("  Input schema:")
                lines.append("  " + schema_text.replace("\n", "\n  "))

            if tool.prompt_path:
                prompt_text = self.repository.read_text(tool.prompt_path)
                if prompt_text:
                    lines.append("  Tool notes:")
                    lines.append("  " + prompt_text.replace("\n", "\n  "))

        return "\n".join(lines)

    def _task_context_section(self, task_context: str) -> str:
        text = task_context.strip()
        if not text:
            text = "Continue the conversation and use tools only when needed."
        return "# Task Context\n" + text

    def _output_schema_section(self, output_schema: dict[str, Any]) -> str:
        schema_text = json.dumps(output_schema, indent=2, sort_keys=True)
        return "\n".join(
            [
                "# Output Contract",
                "Return JSON only.",
                "Your response must validate against this schema:",
                schema_text,
            ]
        )
