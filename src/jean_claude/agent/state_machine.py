from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jean_claude.errors import FlowError
from jean_claude.prompts import FlowDefinition, FlowState


@dataclass(slots=True)
class FlowRuntime:
    definition: FlowDefinition
    current_state_name: str

    @classmethod
    def from_definition(cls, definition: FlowDefinition) -> "FlowRuntime":
        return cls(definition=definition, current_state_name=definition.initial_state)

    def current_state(self) -> FlowState:
        state = self.definition.states.get(self.current_state_name)
        if state is None:
            raise FlowError(f"Unknown flow state: {self.current_state_name}")
        return state

    def transition(self, payload: dict[str, Any]) -> str:
        state = self.current_state()
        for transition in state.transitions:
            if transition.matches(payload):
                self.current_state_name = transition.to
                return self.current_state_name
        self.current_state_name = state.name
        return self.current_state_name
