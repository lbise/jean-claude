# Jean-Claude - Current Plan

## Vision

Jean-Claude is now focused on being a simple, configurable LLM chat assistant.

The immediate goal is not media discovery or recommendation workflows. The goal is a tight chat loop with a prompt file that is easy to inspect and edit.

## Starter Scope

- CLI-based chat interface
- configurable system prompt stored as Markdown
- full system prompt sent on every request
- recent message history appended to each new prompt
- OpenAI Codex provider plus a mock provider for offline work

## Product Direction

### Phase 0: Stable CLI chat core

Build a reliable base that proves:

- authentication works
- prompts are easy to edit locally
- conversation history behaves predictably
- tests cover the main chat loop

### Phase 1: Better prompt and session ergonomics

Potential next additions:

- saved chat transcripts
- named prompt profiles
- session export/import
- richer debug and inspection tools

### Phase 2: Web interface

Once the chat core feels solid, add a simple web UI on top of the same chat/session primitives.

## Architecture Principles

- keep the `LLMClient` abstraction small
- keep prompt text editable from the filesystem
- prefer deterministic tests with a mock client
- avoid product-specific domain logic until the base chat UX is solid

## Immediate Next Step

Keep iterating on the CLI chat experience until it feels like a dependable starter shell for future interfaces.
