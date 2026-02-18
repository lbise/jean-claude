# Prompt Pack

Jean-Claude loads prompts and flow config from the filesystem prompt pack.

## Layout

- `prompts/base/jeanclaude.md`
- `prompts/base/policies.md`
- `prompts/modes/chat.md`
- `prompts/tools/catalog.yaml`
- `prompts/tools/bash.md`
- `prompts/flows/chat.yaml`
- `prompts/schemas/turn.chat.json`

## Layer Order

For each turn, system prompt layers are assembled in this order:

1. base personality
2. global policies
3. mode prompt
4. available tools
5. task context from current flow state
6. output schema contract

User prompt includes:

1. user profile/context JSON
2. flow context JSON
3. latest user message
4. message history JSON

## State Machine

`prompts/flows/chat.yaml` defines state transitions.

Each state provides:

- `task_context`
- `output_schema`
- `tools`
- `transitions`

The runtime executes one LLM call per user turn, validates response shape, runs tool calls, and transitions state.
