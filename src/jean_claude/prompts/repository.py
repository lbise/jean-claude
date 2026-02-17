from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from jean_claude.config import prompts_dir


@dataclass(slots=True)
class FlowTransition:
    to: str
    when_field: str | None = None
    when_equals: Any = None
    has_condition: bool = False

    def matches(self, *, payload: dict[str, Any], state: dict[str, Any]) -> bool:
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
    terminal: bool = False
    skills: list[str] | None = None


@dataclass(slots=True)
class FlowDefinition:
    mode: str
    base_layers: list[str]
    mode_prompt: str
    skills_catalog: str | None
    initial_state: str
    states: dict[str, FlowState]


@dataclass(slots=True)
class SkillDefinition:
    id: str
    name: str
    description: str
    modes: list[str]


class PromptPackRepository:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or prompts_dir()).resolve()

    def resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        try:
            path.relative_to(self.root)
        except ValueError:
            raise ValueError(f"Prompt path escapes prompt pack root: {relative_path}")
        return path

    def read_text(self, relative_path: str) -> str:
        path = self.resolve(relative_path)
        return path.read_text(encoding="utf-8").strip()

    def read_json(self, relative_path: str) -> dict[str, Any]:
        path = self.resolve(relative_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"JSON file must contain an object: {relative_path}")
        return data

    def read_yaml(self, relative_path: str) -> dict[str, Any]:
        path = self.resolve(relative_path)
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"YAML file must contain an object: {relative_path}")
        return loaded

    def load_flow(self, mode: str) -> FlowDefinition:
        flows_dir = self.resolve("flows")
        for flow_file in sorted(flows_dir.glob("*.yaml")):
            loaded = yaml.safe_load(flow_file.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                continue
            if str(loaded.get("mode", "")).strip() != mode:
                continue
            return self._parse_flow(loaded, source=str(flow_file.relative_to(self.root)))

        raise ValueError(f"No flow found for mode '{mode}' in {flows_dir}")

    def load_skills(self, relative_path: str, *, mode: str, enabled_ids: list[str] | None = None) -> list[SkillDefinition]:
        data = self.read_yaml(relative_path)
        skills_raw = data.get("skills")
        if not isinstance(skills_raw, list):
            return []

        enabled_filter = {item for item in enabled_ids} if isinstance(enabled_ids, list) and enabled_ids else None
        skills: list[SkillDefinition] = []
        for item in skills_raw:
            if not isinstance(item, dict):
                continue
            skill_id = str(item.get("id", "")).strip()
            if not skill_id:
                continue

            modes = item.get("modes")
            mode_list = [str(entry).strip() for entry in modes] if isinstance(modes, list) else []
            if mode_list and mode not in mode_list and "*" not in mode_list:
                continue

            if enabled_filter is not None and skill_id not in enabled_filter:
                continue

            name = str(item.get("name", skill_id)).strip() or skill_id
            description = str(item.get("description", "")).strip()
            skills.append(SkillDefinition(id=skill_id, name=name, description=description, modes=mode_list))

        return skills

    def _parse_flow(self, data: dict[str, Any], *, source: str) -> FlowDefinition:
        mode = str(data.get("mode", "")).strip()
        if not mode:
            raise ValueError(f"Flow '{source}' is missing mode")

        initial_state = str(data.get("initial_state", "")).strip()
        if not initial_state:
            raise ValueError(f"Flow '{source}' is missing initial_state")

        base_layers_raw = data.get("base_layers")
        if not isinstance(base_layers_raw, list) or not base_layers_raw:
            raise ValueError(f"Flow '{source}' must define non-empty base_layers")
        base_layers = [str(entry).strip() for entry in base_layers_raw if str(entry).strip()]

        mode_prompt = str(data.get("mode_prompt", "")).strip()
        if not mode_prompt:
            raise ValueError(f"Flow '{source}' is missing mode_prompt")

        skills_catalog = str(data.get("skills_catalog", "")).strip() or None

        states_raw = data.get("states")
        if not isinstance(states_raw, dict) or not states_raw:
            raise ValueError(f"Flow '{source}' must define states")

        states: dict[str, FlowState] = {}
        for state_name, state_data in states_raw.items():
            if not isinstance(state_data, dict):
                raise ValueError(f"Flow '{source}' state '{state_name}' must be an object")

            task_context = str(state_data.get("task_context", "")).strip()
            output_schema = str(state_data.get("output_schema", "")).strip()
            if not output_schema:
                raise ValueError(f"Flow '{source}' state '{state_name}' is missing output_schema")

            terminal = bool(state_data.get("terminal", False))
            transitions_raw = state_data.get("transitions")
            if transitions_raw is None:
                transitions_raw = []
            if not isinstance(transitions_raw, list):
                raise ValueError(f"Flow '{source}' state '{state_name}' transitions must be a list")
            if not transitions_raw and not terminal:
                raise ValueError(f"Flow '{source}' state '{state_name}' must define transitions")

            transitions: list[FlowTransition] = []
            for transition_data in transitions_raw:
                if not isinstance(transition_data, dict):
                    raise ValueError(f"Flow '{source}' state '{state_name}' has invalid transition")
                target = str(transition_data.get("to", "")).strip()
                if not target:
                    raise ValueError(f"Flow '{source}' state '{state_name}' transition missing target")

                when = transition_data.get("when")
                if isinstance(when, dict):
                    field = str(when.get("field", "")).strip()
                    has_equals = "equals" in when
                    if not field or not has_equals:
                        raise ValueError(
                            f"Flow '{source}' state '{state_name}' transition condition needs field and equals"
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

            if not transitions_raw and terminal:
                transitions.append(FlowTransition(to=str(state_name)))

            skills = state_data.get("skills")
            skills_list = [str(item).strip() for item in skills] if isinstance(skills, list) else None
            states[state_name] = FlowState(
                name=str(state_name),
                task_context=task_context,
                output_schema_path=output_schema,
                transitions=transitions,
                terminal=terminal,
                skills=skills_list,
            )

        if initial_state not in states:
            raise ValueError(f"Flow '{source}' initial_state '{initial_state}' does not exist in states")

        for state in states.values():
            for transition in state.transitions:
                if transition.to not in states:
                    raise ValueError(
                        f"Flow '{source}' state '{state.name}' points to unknown state '{transition.to}'"
                    )

        return FlowDefinition(
            mode=mode,
            base_layers=base_layers,
            mode_prompt=mode_prompt,
            skills_catalog=skills_catalog,
            initial_state=initial_state,
            states=states,
        )


def _lookup_path(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    if not path:
        return None
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
