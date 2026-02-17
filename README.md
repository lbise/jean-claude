# Jean-Claude (CLI MVP)

This repository currently contains a minimal CLI implementation for Jean-Claude
with:

- ChatGPT OAuth login for OpenAI Codex subscription access
- OpenAI Codex inference test command
- Mock LLM provider for offline development
- v1 prompt pack for interview, extraction, and ranking flows
- Interactive preference interview flow (`jc prefs interview`)

## Quickstart

1. Create a virtual environment and install:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

2. Log in with ChatGPT OAuth (Codex subscription):

```bash
jc auth login openai-codex
```

3. Run an LLM connectivity test:

```bash
jc llm test --provider openai-codex --model gpt-5.3-codex --prompt "Recommend one sci-fi movie and explain why."
```

4. Run with the local mock provider (no network):

```bash
jc llm test --provider mock --prompt "Find a thriller series"
```

5. Run interactive preference interview:

```bash
jc prefs interview --provider openai-codex --model gpt-5.3-codex
```

## Commands

### Auth

```bash
jc auth login openai-codex
jc auth status openai-codex
jc auth logout openai-codex
```

### LLM

```bash
jc llm test --provider openai-codex --model gpt-5.3-codex --prompt "..."
jc llm test --provider mock --prompt "..."
```

### JSON output

```bash
jc llm test --provider mock --prompt "..." --json
jc prefs show --json
```

### Preferences

```bash
jc prefs interview --provider openai-codex --model gpt-5.3-codex
jc prefs interview --provider mock --max-turns 1
jc prefs show
jc prefs show --json
jc prefs reset
```

## Storage

Credentials are stored at:

- `~/.jean-claude/auth.json`

Preferences are stored at:

- `~/.jean-claude/prefs.json`

You can override this directory with:

- `JEAN_CLAUDE_STATE_DIR`

## Notes

- The OpenAI Codex flow here uses ChatGPT OAuth tokens and Codex backend
  endpoints intended for Codex subscription usage.
- This should be treated as an integration path for testing and experimentation
  while the project remains in MVP mode.

## Prompt pack

- Prompt definitions live in `src/jean_claude/prompts/v1.py`.
- Prompt pack overview lives in `docs/PROMPTS_V1.md`.
