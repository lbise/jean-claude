from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from jean_claude.config import prompts_dir
from jean_claude.errors import FlowError


@dataclass(slots=True)
class ToolDefinition:
    id: str
    name: str
    description: str
    prompt_path: str | None
    modes: list[str]


@dataclass(slots=True)
class FlowTransition:
    to: str
    when_field: str | None = None
    when_equals: Any = None
    has_condition: bool = False

    def matches(self, payload: dict[str, Any]) -> bool:
        if not self.has_condition:
            return True
        value = _lookup_path(payload, self.when_field or "")
        return value == self.when_equals


@dataclass(slots=True)
class FlowState:
    name: str
    task_context: str
    output_schema_path: str
    transitions: list[FlowTransition]
    tools: list[str]
    terminal: bool = False


@dataclass(slots=True)
class FlowDefinition:
    mode: str
    base_layers: list[str]
    mode_prompt: str
    tools_catalog: str | None
    initial_state: str
    states: dict[str, FlowState]


class PromptPackRepository:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or prompts_dir()).resolve()

    def resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise FlowError(f"Prompt path escapes prompt-pack root: {relative_path}") from exc
        return path

    def read_text(self, relative_path: str) -> str:
        path = self.resolve(relative_path)
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise FlowError(f"Unable to read prompt text: {relative_path}") from exc

    def read_json(self, relative_path: str) -> dict[str, Any]:
        path = self.resolve(relative_path)
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise FlowError(f"Unable to read JSON file: {relative_path}") from exc
        except json.JSONDecodeError as exc:
            raise FlowError(f"Invalid JSON in file: {relative_path}") from exc

        if not isinstance(loaded, dict):
            raise FlowError(f"JSON file must contain an object: {relative_path}")
        return loaded

    def read_yaml(self, relative_path: str) -> dict[str, Any]:
        path = self.resolve(relative_path)
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise FlowError(f"Unable to read YAML file: {relative_path}") from exc
        except yaml.YAMLError as exc:
            raise FlowError(f"Invalid YAML in file: {relative_path}") from exc

        if not isinstance(loaded, dict):
            raise FlowError(f"YAML file must contain an object: {relative_path}")
        return loaded

    def load_flow(self, mode: str) -> FlowDefinition:
        flows_dir = self.resolve("flows")
        for path in sorted(flows_dir.glob("*.yaml")):
            try:
                loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as exc:
                raise FlowError(f"Unable to parse flow file: {path.name}") from exc
            if not isinstance(loaded, dict):
                continue
            if str(loaded.get("mode", "")).strip() != mode:
                continue
            return self._parse_flow(loaded, source=str(path.relative_to(self.root)))

        raise FlowError(f"No flow found for mode '{mode}' in {flows_dir}")

    def load_tools(
        self,
        relative_path: str,
        *,
        mode: str,
        enabled_ids: list[str] | None = None,
    ) -> list[ToolDefinition]:
        data = self.read_yaml(relative_path)
        tools_raw = data.get("tools")
        if not isinstance(tools_raw, list):
            return []

        enabled = {item for item in enabled_ids} if isinstance(enabled_ids, list) else None
        tools: list[ToolDefinition] = []

        for item in tools_raw:
            if not isinstance(item, dict):
                continue
            tool_id = str(item.get("id", "")).strip()
            if not tool_id:
                continue

            modes = item.get("modes")
            mode_list = [str(entry).strip() for entry in modes] if isinstance(modes, list) else []
            if mode_list and mode not in mode_list and "*" not in mode_list:
                continue

            if enabled is not None and tool_id not in enabled:
                continue

            tools.append(
                ToolDefinition(
                    id=tool_id,
                    name=str(item.get("name", tool_id)).strip() or tool_id,
                    description=str(item.get("description", "")).strip(),
                    prompt_path=str(item.get("prompt", "")).strip() or None,
                    modes=mode_list,
                )
            )

        return tools

    def _parse_flow(self, data: dict[str, Any], *, source: str) -> FlowDefinition:
        mode = str(data.get("mode", "")).strip()
        if not mode:
            raise FlowError(f"Flow '{source}' missing mode")

        initial_state = str(data.get("initial_state", "")).strip()
        if not initial_state:
            raise FlowError(f"Flow '{source}' missing initial_state")

        base_layers_raw = data.get("base_layers")
        if not isinstance(base_layers_raw, list) or not base_layers_raw:
            raise FlowError(f"Flow '{source}' must define non-empty base_layers")
        base_layers = [str(item).strip() for item in base_layers_raw if str(item).strip()]

        mode_prompt = str(data.get("mode_prompt", "")).strip()
        if not mode_prompt:
            raise FlowError(f"Flow '{source}' missing mode_prompt")

        tools_catalog = str(data.get("tools_catalog", "")).strip() or None
        states_raw = data.get("states")
        if not isinstance(states_raw, dict) or not states_raw:
            raise FlowError(f"Flow '{source}' must define states")

        states: dict[str, FlowState] = {}
        for state_name, state_data in states_raw.items():
            if not isinstance(state_data, dict):
                raise FlowError(f"Flow '{source}' state '{state_name}' must be an object")

            output_schema = str(state_data.get("output_schema", "")).strip()
            if not output_schema:
                raise FlowError(f"Flow '{source}' state '{state_name}' missing output_schema")

            transitions_raw = state_data.get("transitions")
            terminal = bool(state_data.get("terminal", False))
            if transitions_raw is None:
                transitions_raw = []
            if not isinstance(transitions_raw, list):
                raise FlowError(f"Flow '{source}' state '{state_name}' transitions must be a list")
            if not transitions_raw and not terminal:
                raise FlowError(f"Flow '{source}' state '{state_name}' must define transitions")

            transitions: list[FlowTransition] = []
            for transition_data in transitions_raw:
                if not isinstance(transition_data, dict):
                    raise FlowError(f"Flow '{source}' state '{state_name}' has invalid transition")
                target = str(transition_data.get("to", "")).strip()
                if not target:
                    raise FlowError(f"Flow '{source}' state '{state_name}' transition missing target")

                when = transition_data.get("when")
                if isinstance(when, dict):
                    field = str(when.get("field", "")).strip()
                    if not field or "equals" not in when:
                        raise FlowError(
                            f"Flow '{source}' state '{state_name}' transition condition requires field and equals"
                        )
                    transitions.append(
                        FlowTransition(
                            to=target,
                            when_field=field,
                            when_equals=when.get("equals"),
                            has_condition=True,
                        )
                    )
                else:
                    transitions.append(FlowTransition(to=target))

            if not transitions and terminal:
                transitions.append(FlowTransition(to=str(state_name)))

            tools_raw = state_data.get("tools")
            tool_ids = [str(item).strip() for item in tools_raw] if isinstance(tools_raw, list) else []

            states[str(state_name)] = FlowState(
                name=str(state_name),
                task_context=str(state_data.get("task_context", "")).strip(),
                output_schema_path=output_schema,
                transitions=transitions,
                tools=tool_ids,
                terminal=terminal,
            )

        if initial_state not in states:
            raise FlowError(f"Flow '{source}' initial_state '{initial_state}' not found in states")

        for state in states.values():
            for transition in state.transitions:
                if transition.to not in states:
                    raise FlowError(
                        f"Flow '{source}' state '{state.name}' points to unknown state '{transition.to}'"
                    )

        return FlowDefinition(
            mode=mode,
            base_layers=base_layers,
            mode_prompt=mode_prompt,
            tools_catalog=tools_catalog,
            initial_state=initial_state,
            states=states,
        )


def _lookup_path(payload: dict[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    if not dotted_path:
        return None
    for segment in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
    return current
