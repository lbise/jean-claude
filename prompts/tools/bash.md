# Tool: bash.run

Use this tool when the user asks for information or actions that require shell execution.

Guidelines:
- In default policy mode, commands are restricted by allowlist.
- Prefer read-only commands unless the user explicitly asks to modify the system.
- Keep commands minimal and deterministic.
- Return tool calls with a single `command` string in args.

Example tool call:

```json
{
  "tool": "bash.run",
  "args": {
    "command": "ls -la ~"
  }
}
```
