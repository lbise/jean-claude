"""Prompt-pack loading from editable filesystem files."""

from .repository import (
    FlowDefinition,
    FlowState,
    FlowTransition,
    PromptPackRepository,
    SkillDefinition,
)


def default_base_instructions(repository: PromptPackRepository | None = None) -> str:
    repo = repository or PromptPackRepository()
    try:
        system_prompt = repo.read_text("system.md")
    except Exception:
        system_prompt = ""
    if system_prompt:
        return system_prompt

    parts = [
        repo.read_text("base/jeanclaude.md"),
        repo.read_text("base/policies.md"),
    ]
    return "\n\n".join(part for part in parts if part)


__all__ = [
    "FlowDefinition",
    "FlowState",
    "FlowTransition",
    "PromptPackRepository",
    "SkillDefinition",
    "default_base_instructions",
]
