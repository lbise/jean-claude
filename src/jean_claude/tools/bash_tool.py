from __future__ import annotations

import subprocess
import time
from typing import Any

from jean_claude.errors import ToolError
from jean_claude.tools.base import ToolContext, ToolResult
from jean_claude.tools.policy import BashPolicy


DEFAULT_TIMEOUT_SECONDS = 30
MAX_OUTPUT_CHARS = 12000


class BashRunTool:
    id = "bash.run"
    name = "Run Bash Command"
    description = "Execute a bash command on the local machine"
    input_schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["command"],
        "properties": {
            "command": {"type": "string"},
            "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 300},
            "working_directory": {"type": "string"},
        },
    }

    def __init__(self, policy: BashPolicy) -> None:
        self.policy = policy

    def run(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        command = _as_text(args.get("command"))
        timeout_seconds = _as_timeout(args.get("timeout_seconds"))
        working_directory = _as_text(args.get("working_directory"))
        plan = self.policy.plan(command=command, working_directory=working_directory)

        try:
            started = time.time()
            if plan.mode == "unrestricted":
                process = subprocess.run(
                    ["/bin/bash", "-lc", plan.shell_command or ""],
                    cwd=str(plan.working_directory) if plan.working_directory else None,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
            else:
                process = subprocess.run(
                    plan.argv or [],
                    cwd=str(plan.working_directory) if plan.working_directory else None,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
            elapsed_ms = int((time.time() - started) * 1000)
        except subprocess.TimeoutExpired as exc:
            return ToolResult(
                tool=self.id,
                ok=False,
                output=f"Command timed out after {timeout_seconds}s",
                exit_code=None,
                metadata={"timeout_seconds": timeout_seconds, "partial_output": _truncate((exc.stdout or "") + (exc.stderr or ""))},
            )
        except OSError as exc:
            raise ToolError(f"Failed to execute command: {exc}") from exc

        merged_output = _merge_streams(process.stdout, process.stderr)
        return ToolResult(
            tool=self.id,
            ok=process.returncode == 0,
            output=_truncate(merged_output),
            exit_code=process.returncode,
            metadata={
                "policy_mode": plan.mode,
                "elapsed_ms": elapsed_ms,
                "working_directory": str(plan.working_directory) if plan.working_directory else None,
            },
        )


def _as_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_timeout(value: object) -> int:
    if isinstance(value, int) and 1 <= value <= 300:
        return value
    return DEFAULT_TIMEOUT_SECONDS


def _merge_streams(stdout: str, stderr: str) -> str:
    out = stdout.rstrip()
    err = stderr.rstrip()
    if out and err:
        return f"{out}\n\n[stderr]\n{err}"
    if err:
        return f"[stderr]\n{err}"
    return out


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n\n[truncated]"
