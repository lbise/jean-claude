from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from jean_claude.config import prefs_file_path
from jean_claude.errors import JeanClaudeError
from jean_claude.prefs.profile import default_user_profile, normalize_user_profile


class PreferencesStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or prefs_file_path()

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return default_user_profile()
        try:
            content = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise JeanClaudeError(f"Unable to read preferences store: {self.path}") from exc
        if not content.strip():
            return default_user_profile()
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise JeanClaudeError(f"Preferences file is not valid JSON: {self.path}") from exc
        return normalize_user_profile(data if isinstance(data, dict) else None)

    def save(self, profile: dict[str, Any]) -> None:
        normalized = normalize_user_profile(profile)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass

        payload = json.dumps(normalized, indent=2, sort_keys=True) + "\n"
        fd, temp_name = tempfile.mkstemp(prefix=".prefs-", dir=str(self.path.parent), text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file_handle:
                file_handle.write(payload)
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
            raise JeanClaudeError(f"Unable to write preferences store: {self.path}") from exc
