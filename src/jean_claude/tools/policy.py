from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path

from jean_claude.errors import ToolError
from jean_claude.tools.settings import ToolSettings


POLICY_ALLOWLIST = "allowlist"
POLICY_UNRESTRICTED = "unrestricted"


@dataclass(slots=True)
class BashExecutionPlan:
    mode: str
    argv: list[str] | None = None
    shell_command: str | None = None
    working_directory: Path | None = None


class BashPolicy:
    def __init__(self, settings: ToolSettings) -> None:
        self.settings = settings

    def mode(self) -> str:
        raw = self.settings.execution_policy.strip().lower()
        if raw == POLICY_UNRESTRICTED:
            return POLICY_UNRESTRICTED
        return POLICY_ALLOWLIST

    def plan(self, *, command: str, working_directory: str | None = None) -> BashExecutionPlan:
        command_text = command.strip()
        if not command_text:
            raise ToolError("bash.run requires a non-empty command")

        cwd_path = self._normalize_workdir(working_directory)
        mode = self.mode()
        if mode == POLICY_UNRESTRICTED:
            return BashExecutionPlan(
                mode=mode,
                shell_command=command_text,
                working_directory=cwd_path,
            )

        try:
            argv = shlex.split(command_text, posix=True)
        except ValueError as exc:
            raise ToolError(f"Unable to parse bash command: {exc}") from exc

        if not argv:
            raise ToolError("bash.run command has no executable")

        argv = [os.path.expanduser(item) if item.startswith("~") else item for item in argv]

        executable = Path(argv[0]).name
        allowed = {item.strip() for item in self.settings.normalized_allowlist() if item.strip()}
        if executable not in allowed:
            raise ToolError(
                f"Command '{executable}' is blocked by allowlist policy. "
                "Use 'jc tools policy set unrestricted --yes-i-understand' to override."
            )

        return BashExecutionPlan(mode=mode, argv=argv, working_directory=cwd_path)

    def _normalize_workdir(self, raw: str | None) -> Path | None:
        if not raw:
            return None
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise ToolError(f"Working directory does not exist: {path}")
        if not path.is_dir():
            raise ToolError(f"Working directory is not a directory: {path}")
        return path
