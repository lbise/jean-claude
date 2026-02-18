from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from jean_claude.agent.prompt_builder import PromptBuilder
from jean_claude.agent.session import AgentSession, ChatMessage
from jean_claude.agent.state_machine import FlowRuntime
from jean_claude.errors import FlowError, LLMError, ToolError
from jean_claude.llm.base import DebugHook, LLMClient
from jean_claude.prompts import PromptPackRepository
from jean_claude.tools import ToolCall, ToolContext, ToolRegistry


@dataclass(slots=True)
class AgentTurnResult:
    assistant_message: str
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    raw_payload: dict[str, Any] | None = None


class AgentOrchestrator:
    def __init__(
        self,
        *,
        llm_client: LLMClient,
        model: str,
        mode: str = "chat",
        prompt_repository: PromptPackRepository | None = None,
        tool_registry: ToolRegistry,
        debug_hook: DebugHook | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.model = model
        self.mode = mode
        self.prompt_repository = prompt_repository or PromptPackRepository()
        self.tool_registry = tool_registry
        self.debug_hook = debug_hook

        self.flow = self.prompt_repository.load_flow(mode)
        self.runtime = FlowRuntime.from_definition(self.flow)
        self.prompt_builder = PromptBuilder(self.prompt_repository, self.tool_registry)

        self.session = AgentSession(
            session_id=uuid.uuid4().hex,
            flow_state=self.runtime.current_state_name,
            user_profile={},
            history=[],
        )

    def handle_user_message(self, user_message: str) -> AgentTurnResult:
        latest = user_message.strip()
        if not latest:
            raise FlowError("User message must not be empty")

        current_state = self.runtime.current_state()
        output_schema = self.prompt_repository.read_json(current_state.output_schema_path)
        enabled_tools = self._enabled_tools(current_state.tools)

        system_prompt = self.prompt_builder.build_system_prompt(
            flow=self.flow,
            state=current_state,
            tools=enabled_tools,
            output_schema=output_schema,
        )
        user_prompt = self.prompt_builder.build_user_prompt(
            mode=self.mode,
            flow_state=self.runtime.current_state_name,
            user_profile=self.session.user_profile,
            latest_user_message=latest,
            message_history=self.session.history,
        )

        self.session.history.append(ChatMessage(role="user", content=latest))

        self._emit_debug(
            {
                "type": "agent.turn.request",
                "mode": self.mode,
                "flow_state": self.runtime.current_state_name,
                "system_prompt": system_prompt,
                "prompt": user_prompt,
            }
        )

        response = self.llm_client.complete(
            user_prompt,
            model=self.model,
            system_prompt=system_prompt,
            debug_hook=self.debug_hook,
        )
        payload = self._parse_model_payload(response.text)
        self._validate_payload(payload=payload, schema=output_schema)

        tool_results = self._execute_tool_calls(payload=payload, allowed_tools={tool.id for tool in enabled_tools})
        self._apply_profile_patch(payload)

        next_state = self.runtime.transition(payload)
        self.session.flow_state = next_state

        assistant_message = self._final_assistant_message(payload, tool_results)
        self.session.history.append(ChatMessage(role="assistant", content=assistant_message))

        self._emit_debug(
            {
                "type": "agent.turn.response",
                "mode": self.mode,
                "flow_state": next_state,
                "assistant_message": assistant_message,
                "payload": payload,
                "tool_results": tool_results,
            }
        )

        return AgentTurnResult(
            assistant_message=assistant_message,
            tool_results=tool_results,
            raw_payload=payload,
        )

    def _enabled_tools(self, state_tools: list[str]) -> list[Any]:
        if not self.flow.tools_catalog:
            return []
        return self.prompt_repository.load_tools(
            self.flow.tools_catalog,
            mode=self.mode,
            enabled_ids=state_tools,
        )

    def _execute_tool_calls(self, *, payload: dict[str, Any], allowed_tools: set[str]) -> list[dict[str, Any]]:
        raw_calls = payload.get("tool_calls")
        if not isinstance(raw_calls, list):
            return []

        results: list[dict[str, Any]] = []
        for raw_call in raw_calls:
            if not isinstance(raw_call, dict):
                continue
            tool_id = str(raw_call.get("tool", "")).strip()
            args = raw_call.get("args")
            if not tool_id:
                continue

            try:
                if tool_id not in allowed_tools:
                    raise ToolError(f"Tool '{tool_id}' is not allowed in flow state '{self.runtime.current_state_name}'")
                if not isinstance(args, dict):
                    raise ToolError(f"Tool '{tool_id}' requires args object")

                result = self.tool_registry.invoke(
                    ToolCall(tool=tool_id, args=args),
                    context=ToolContext(session_id=self.session.session_id),
                )
                tool_payload = {
                    "tool": result.tool,
                    "ok": result.ok,
                    "exit_code": result.exit_code,
                    "output": result.output,
                    "metadata": result.metadata,
                }
            except ToolError as exc:
                tool_payload = {
                    "tool": tool_id,
                    "ok": False,
                    "exit_code": None,
                    "output": str(exc),
                    "metadata": {"error": "tool_error"},
                }
            results.append(tool_payload)
            self.session.history.append(
                ChatMessage(
                    role="tool",
                    content=json.dumps(tool_payload, indent=2, sort_keys=True),
                )
            )

        return results

    def _apply_profile_patch(self, payload: dict[str, Any]) -> None:
        patch = payload.get("profile_patch")
        if isinstance(patch, dict):
            merged = dict(self.session.user_profile)
            merged.update(patch)
            self.session.user_profile = merged

    def _final_assistant_message(self, payload: dict[str, Any], tool_results: list[dict[str, Any]]) -> str:
        assistant_message = str(payload.get("assistant_message", "")).strip()
        if tool_results:
            tool_block = self._render_tool_results(tool_results)
            if assistant_message:
                return f"{assistant_message}\n\n{tool_block}"
            return tool_block
        if assistant_message:
            return assistant_message
        return "Done."

    def _render_tool_results(self, tool_results: list[dict[str, Any]]) -> str:
        lines = ["Tool results:"]
        for item in tool_results:
            status = "ok" if item.get("ok") else "error"
            lines.append(f"- {item.get('tool')} ({status})")
            output = str(item.get("output", "")).strip()
            if output:
                lines.append(output)
        return "\n".join(lines)

    def _parse_model_payload(self, text: str) -> dict[str, Any]:
        stripped = text.strip()
        if not stripped:
            raise LLMError("Model returned empty output")

        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = self._extract_embedded_json(stripped)

        if not isinstance(payload, dict):
            raise LLMError("Model output is not a JSON object")
        return payload

    def _extract_embedded_json(self, text: str) -> dict[str, Any]:
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                candidate = "\n".join(lines[1:-1]).strip()
                try:
                    payload = json.loads(candidate)
                    if isinstance(payload, dict):
                        return payload
                except json.JSONDecodeError:
                    pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                payload = json.loads(candidate)
                if isinstance(payload, dict):
                    return payload
            except json.JSONDecodeError:
                pass

        raise LLMError("Model output is not valid JSON")

    def _validate_payload(self, *, payload: dict[str, Any], schema: dict[str, Any]) -> None:
        required = schema.get("required")
        if isinstance(required, list):
            missing = [key for key in required if key not in payload]
            if missing:
                raise LLMError(f"Model output missing required fields: {', '.join(missing)}")

        if schema.get("additionalProperties") is False:
            properties = schema.get("properties")
            if isinstance(properties, dict):
                extra = sorted(set(payload.keys()) - set(properties.keys()))
                if extra:
                    raise LLMError(f"Model output has unexpected fields: {', '.join(extra)}")

    def _emit_debug(self, payload: dict[str, Any]) -> None:
        if self.debug_hook is not None:
            self.debug_hook(payload)
