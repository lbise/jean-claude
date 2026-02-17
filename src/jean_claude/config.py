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


def prefs_file_path() -> Path:
    return state_dir() / "prefs.json"
