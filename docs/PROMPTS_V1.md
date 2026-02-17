# Jean-Claude Prompt System (v1)

The prompt system is now file-driven and outside application code.

## Prompt Pack Layout

- `prompts/base/jeanclaude.md`
- `prompts/base/policies.md`
- `prompts/modes/onboarding.md`
- `prompts/modes/chat.md`
- `prompts/skills/catalog.yaml`
- `prompts/flows/onboarding.yaml`
- `prompts/flows/chat.yaml`
- `prompts/schemas/turn.onboarding.json`
- `prompts/schemas/turn.chat.json`

## Layer Order (per turn)

1. Base personality (`jeanclaude.md`)
2. Global policies (`policies.md`)
3. Mode prompt (`modes/<mode>.md`)
4. Available skills section (`skills/catalog.yaml` filtered by mode)
5. User context pack (profile)
6. Task context (from current flow state)
7. Message history and latest user message

## Flow State Machine

Each mode uses a YAML flow in `prompts/flows/`.

Flow responsibilities:

- define `initial_state`
- define per-state `task_context`
- define per-state `output_schema`
- define state transitions via simple `when.field == when.equals`

The conversation engine executes one model call per turn, validates required schema fields,
applies patches, then transitions state.

## Runtime Modules

- Prompt pack loading: `src/jean_claude/prompts/repository.py`
- State-machine orchestration: `src/jean_claude/conversation/engine.py`

## Config

- Default prompt pack path: `./prompts` (or discovered parent prompt folder)
- Override with `JEAN_CLAUDE_PROMPTS_DIR`
