from __future__ import annotations

import os
from pathlib import Path


DEFAULT_STATE_DIR = Path.home() / ".jean-claude"


def state_dir() -> Path:
    raw = os.getenv("JEAN_CLAUDE_STATE_DIR", "").strip()
    if not raw:
        return DEFAULT_STATE_DIR
    return Path(raw).expanduser().resolve()


def auth_file_path() -> Path:
    return state_dir() / "auth.json"


def default_system_prompt_path() -> Path:
    return prompts_dir() / "system.md"


def prompts_dir() -> Path:
    env_override = os.getenv("JEAN_CLAUDE_PROMPTS_DIR", "").strip()
    if env_override:
        return Path(env_override).expanduser().resolve()

    for candidate in _prompt_dir_candidates():
        if candidate.is_dir():
            return candidate

    return (Path.cwd() / "prompts").resolve()


def _prompt_dir_candidates() -> list[Path]:
    module_path = Path(__file__).resolve()
    cwd = Path.cwd().resolve()
    return [
        cwd / "prompts",
        module_path.parents[2] / "prompts",
        module_path.parents[3] / "prompts",
    ]
