from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from jean_claude.errors import LLMError
from jean_claude.llm.base import DebugHook, LLMClient
from jean_claude.prefs.profile import normalize_user_profile
from jean_claude.prompts import PromptPackRepository


ONBOARDING_MODE = "onboarding_interview"
OPEN_CHAT_MODE = "open_chat"


@dataclass(slots=True)
class ConversationTurnResult:
    assistant_message: str
    next_question: str
    done: bool
    state: dict[str, Any]
    payload: dict[str, Any]
    flow_state: str


class ConversationEngine:
    def __init__(
        self,
        *,
        client: LLMClient,
        model: str,
        mode: str,
        initial_state: dict[str, Any] | None = None,
        history_turn_limit: int = 8,
        debug_hook: DebugHook | None = None,
        prompt_repository: PromptPackRepository | None = None,
    ) -> None:
        self.client = client
        self.model = model
        self.mode = mode
        self.history_turn_limit = max(1, history_turn_limit)
        self.debug_hook = debug_hook
        self.repo = prompt_repository or PromptPackRepository()
        try:
            self.flow = self.repo.load_flow(mode)
        except Exception as exc:  # pragma: no cover - guarded by tests that use valid prompt pack
            raise LLMError(f"Unable to load flow for mode '{mode}': {exc}") from exc
        self.flow_state_name = self.flow.initial_state
        self.state = self._init_state(mode=mode, initial_state=initial_state)
        self.history: list[dict[str, str]] = []
        self._started = False

    def start(self) -> ConversationTurnResult:
        if self._started:
            raise LLMError("Conversation already started")
        self._started = True
        return self._run_turn(event="session_start", latest_user_message="")

    def reply(self, user_message: str) -> ConversationTurnResult:
        if not self._started:
            self._started = True

        message = user_message.strip()
        if not message:
            raise LLMError("User message must not be empty")

        self.history.append({"role": "user", "content": message})
        return self._run_turn(event="user_message", latest_user_message=message)

    def _run_turn(self, *, event: str, latest_user_message: str) -> ConversationTurnResult:
        state_config = self._require_flow_state(self.flow_state_name)
        try:
            schema = self.repo.read_json(state_config.output_schema_path)
        except Exception as exc:
            raise LLMError(f"Unable to load output schema '{state_config.output_schema_path}': {exc}") from exc
        skills = self._resolve_skills(state_config.skills)
        system_prompt = self._build_system_prompt(state_config=state_config, output_schema=schema, skills=skills)
        user_prompt = self._build_user_prompt(event=event, latest_user_message=latest_user_message)

        _emit_debug(
            self.debug_hook,
            {
                "type": "conversation.turn.request",
                "mode": self.mode,
                "flow_state": self.flow_state_name,
                "event": event,
                "system_prompt": system_prompt,
                "prompt": user_prompt,
                "state": self.state,
            },
        )

        result = self.client.complete(
            user_prompt,
            model=self.model,
            system_prompt=system_prompt,
            debug_hook=self.debug_hook,
        )
        payload = _parse_json_payload(result.text)
        _validate_payload_against_schema(payload=payload, schema=schema)
        self._apply_payload(payload)

        assistant_message = _safe_text(payload.get("assistant_message"), default="")
        next_question = _safe_text(payload.get("next_question"), default="")
        done = bool(payload.get("done"))

        if assistant_message:
            self.history.append({"role": "assistant", "content": assistant_message})
        if next_question:
            self.history.append({"role": "assistant", "content": next_question})

        self.flow_state_name = self._next_flow_state(state_config=state_config, payload=payload)
        done = done or self._require_flow_state(self.flow_state_name).terminal

        _emit_debug(
            self.debug_hook,
            {
                "type": "conversation.turn.response",
                "mode": self.mode,
                "flow_state": self.flow_state_name,
                "event": event,
                "assistant_message": assistant_message,
                "next_question": next_question,
                "done": done,
                "state": self.state,
                "payload": payload,
            },
        )

        return ConversationTurnResult(
            assistant_message=assistant_message,
            next_question=next_question,
            done=done,
            state=dict(self.state),
            payload=payload,
            flow_state=self.flow_state_name,
        )

    def _build_system_prompt(self, *, state_config: Any, output_schema: dict[str, Any], skills: list[dict[str, str]]) -> str:
        parts: list[str] = []
        for relative_path in self.flow.base_layers:
            try:
                text = self.repo.read_text(relative_path)
            except Exception as exc:
                raise LLMError(f"Unable to load base prompt layer '{relative_path}': {exc}") from exc
            if text:
                parts.append(text)

        try:
            mode_prompt = self.repo.read_text(self.flow.mode_prompt)
        except Exception as exc:
            raise LLMError(f"Unable to load mode prompt '{self.flow.mode_prompt}': {exc}") from exc
        if mode_prompt:
            parts.append(mode_prompt)

        parts.append(_render_skills_section(skills))
        parts.append(_render_task_context(state_config.task_context))
        parts.append(_render_output_contract(output_schema))
        return "\n\n".join(part for part in parts if part)

    def _build_user_prompt(self, *, event: str, latest_user_message: str) -> str:
        profile = self.state.get("profile", {})
        history = self._recent_history()
        flow_context = {
            "mode": self.mode,
            "flow_state": self.flow_state_name,
            "event": event,
        }

        sections = [
            "[USER_PROFILE_JSON]",
            json.dumps(profile, indent=2, sort_keys=True),
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
            json.dumps(history, indent=2, sort_keys=True),
            "[/MESSAGE_HISTORY_JSON]",
        ]
        return "\n".join(sections)

    def _resolve_skills(self, state_skill_ids: list[str] | None) -> list[dict[str, str]]:
        if not self.flow.skills_catalog:
            return []

        try:
            skills = self.repo.load_skills(self.flow.skills_catalog, mode=self.mode, enabled_ids=state_skill_ids)
        except Exception as exc:
            raise LLMError(f"Unable to load skills catalog '{self.flow.skills_catalog}': {exc}") from exc
        return [
            {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
            }
            for skill in skills
        ]

    def _apply_payload(self, payload: dict[str, Any]) -> None:
        state_patch = payload.get("state_patch")
        if isinstance(state_patch, dict):
            merged_state = dict(self.state)
            merged_state.update(state_patch)
            self.state = merged_state

        profile_patch = payload.get("profile_patch")
        if isinstance(profile_patch, dict):
            merged = dict(self.state.get("profile", {}))
            merged.update(profile_patch)
            self.state["profile"] = normalize_user_profile(merged)

    def _next_flow_state(self, *, state_config: Any, payload: dict[str, Any]) -> str:
        for transition in state_config.transitions:
            if transition.matches(payload=payload, state=self.state):
                return transition.to
        return state_config.name

    def _require_flow_state(self, state_name: str):
        state = self.flow.states.get(state_name)
        if state is None:
            raise LLMError(f"Flow state not found: {state_name}")
        return state

    def _recent_history(self) -> list[dict[str, str]]:
        max_messages = self.history_turn_limit * 2
        if len(self.history) <= max_messages:
            return list(self.history)
        return self.history[-max_messages:]

    def _init_state(self, *, mode: str, initial_state: dict[str, Any] | None) -> dict[str, Any]:
        state = initial_state if isinstance(initial_state, dict) else {}
        if mode in {ONBOARDING_MODE, OPEN_CHAT_MODE}:
            profile = state.get("profile") if isinstance(state.get("profile"), dict) else state
            return {"profile": normalize_user_profile(profile if isinstance(profile, dict) else None)}
        return dict(state)


def _render_skills_section(skills: list[dict[str, str]]) -> str:
    lines = ["# Available Skills"]
    if not skills:
        lines.append("- none")
        return "\n".join(lines)

    for skill in skills:
        lines.append(f"- `{skill['id']}`: {skill['name']} - {skill['description']}")
    return "\n".join(lines)


def _render_task_context(task_context: str) -> str:
    task = task_context.strip() if isinstance(task_context, str) else ""
    if not task:
        task = "Continue this mode according to policy and context."
    return "# Task Context\n" + task


def _render_output_contract(schema: dict[str, Any]) -> str:
    schema_json = json.dumps(schema, indent=2, sort_keys=True)
    return "\n".join(
        [
            "# Output Contract",
            "Return JSON only.",
            "Your response must validate against this schema:",
            schema_json,
        ]
    )


def _parse_json_payload(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise LLMError("Model returned empty output")

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        payload = _extract_embedded_json(stripped)

    if not isinstance(payload, dict):
        raise LLMError("Model output is not a JSON object")
    return payload


def _extract_embedded_json(text: str) -> dict[str, Any]:
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


def _safe_text(value: Any, *, default: str) -> str:
    if isinstance(value, str):
        return value.strip()
    return default


def _emit_debug(debug_hook: DebugHook | None, payload: dict[str, Any]) -> None:
    if debug_hook is not None:
        debug_hook(payload)


def _validate_payload_against_schema(*, payload: dict[str, Any], schema: dict[str, Any]) -> None:
    required = schema.get("required")
    if isinstance(required, list):
        missing = [key for key in required if key not in payload]
        if missing:
            raise LLMError(f"Model output missing required fields: {', '.join(missing)}")

    additional_props = schema.get("additionalProperties")
    properties = schema.get("properties")
    if additional_props is False and isinstance(properties, dict):
        allowed = set(properties.keys())
        extras = sorted(set(payload.keys()) - allowed)
        if extras:
            raise LLMError(f"Model output has unexpected fields: {', '.join(extras)}")
