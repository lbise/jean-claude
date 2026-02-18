from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jean_claude.config import settings_file_path
from jean_claude.errors import ToolError


DEFAULT_BASH_ALLOWLIST = [
    "ls",
    "pwd",
    "whoami",
    "date",
    "uname",
    "id",
    "cat",
    "head",
    "tail",
    "wc",
    "stat",
    "du",
    "df",
    "echo",
    "which",
    "python",
    "python3",
]


@dataclass(slots=True)
class ToolSettings:
    execution_policy: str = "allowlist"
    bash_allowlist: list[str] | None = None

    def normalized_allowlist(self) -> list[str]:
        if isinstance(self.bash_allowlist, list) and self.bash_allowlist:
            return [item for item in self.bash_allowlist if isinstance(item, str) and item.strip()]
        return list(DEFAULT_BASH_ALLOWLIST)


class ToolSettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings_file_path()

    def load(self) -> ToolSettings:
        raw = self._load_raw()
        policy = str(raw.get("execution_policy", "allowlist")).strip() or "allowlist"
        allowlist_raw = raw.get("bash_allowlist")
        allowlist = allowlist_raw if isinstance(allowlist_raw, list) else None
        return ToolSettings(execution_policy=policy, bash_allowlist=allowlist)

    def save(self, settings: ToolSettings) -> None:
        payload = {
            "execution_policy": settings.execution_policy,
            "bash_allowlist": settings.normalized_allowlist(),
        }
        self._save_raw(payload)

    def _load_raw(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            content = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ToolError(f"Unable to read tool settings: {self.path}") from exc
        if not content.strip():
            return {}
        try:
            loaded = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ToolError(f"Tool settings are not valid JSON: {self.path}") from exc
        if not isinstance(loaded, dict):
            raise ToolError("Tool settings root must be a JSON object")
        return loaded

    def _save_raw(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass

        payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
        fd, temp_name = tempfile.mkstemp(prefix=".settings-", dir=str(self.path.parent), text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            try:
                os.chmod(temp_name, 0o600)
            except OSError:
                pass
            os.replace(temp_name, self.path)
        except OSError as exc:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise ToolError(f"Unable to write tool settings: {self.path}") from exc
