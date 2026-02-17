from __future__ import annotations

from typing import Callable

from jean_claude.conversation import ConversationEngine
from jean_claude.conversation.engine import ONBOARDING_MODE
from jean_claude.errors import JeanClaudeError, LLMError
from jean_claude.llm.base import DebugHook, LLMClient
from jean_claude.prefs.profile import summarize_profile
from jean_claude.prefs.store import PreferencesStore


InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


def run_interview(
    *,
    client: LLMClient,
    model: str,
    store: PreferencesStore,
    max_turns: int = 8,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    debug_hook: DebugHook | None = None,
) -> dict[str, object]:
    profile = store.load()
    engine = ConversationEngine(
        client=client,
        model=model,
        mode=ONBOARDING_MODE,
        initial_state={"profile": profile},
        history_turn_limit=max_turns,
        debug_hook=debug_hook,
    )

    output_fn("Jean-Claude: Let us tune your taste profile.")
    output_fn("Jean-Claude: Commands: /summary, /done, /skip")

    try:
        turn = engine.start()
    except LLMError as exc:
        raise JeanClaudeError(f"Failed to start onboarding interview: {exc}") from exc

    question = _resolve_question(turn.next_question, fallback="What do you usually enjoy watching?")
    if turn.assistant_message:
        output_fn(f"Jean-Claude: {turn.assistant_message}")

    turns = 0
    while turns < max_turns:
        output_fn(f"\nJean-Claude: {question}")
        user_message = input_fn("You: ").strip()
        if not user_message:
            output_fn("Jean-Claude: I did not catch that. Give me a short answer, or type /skip.")
            continue

        command = user_message.casefold()
        if command in {"/summary", "/show"}:
            _print_summary(engine.state.get("profile", {}), output_fn)
            continue
        if command in {"/done", "/finish"}:
            break
        if command == "/skip":
            user_message = "skip this question"

        try:
            turn = engine.reply(user_message)
        except LLMError as exc:
            raise JeanClaudeError(f"Interview turn failed: {exc}") from exc

        profile_state = engine.state.get("profile", {})
        store.save(profile_state)
        turns += 1

        if turn.assistant_message:
            output_fn(f"Jean-Claude: {turn.assistant_message}")

        if turn.done:
            break

        question = _resolve_question(
            turn.next_question,
            fallback="What is one more preference I should know before recommending titles?",
        )

    profile_state = engine.state.get("profile", {})
    _print_summary(profile_state, output_fn)
    confirmation = input_fn("Jean-Claude: Did I get this right? [Y/n]: ").strip().casefold()
    if confirmation in {"", "y", "yes"}:
        output_fn("Jean-Claude: Great. I saved your baseline preferences.")
    else:
        output_fn("Jean-Claude: Got it. You can run the interview again to refine your profile.")

    store.save(profile_state)
    return profile_state


def _resolve_question(value: str, *, fallback: str) -> str:
    text = value.strip() if isinstance(value, str) else ""
    return text or fallback


def _print_summary(profile: dict[str, object], output_fn: OutputFn) -> None:
    output_fn("\nJean-Claude: Here is what I understood:")
    for line in summarize_profile(profile):
        output_fn(f"- {line}")
