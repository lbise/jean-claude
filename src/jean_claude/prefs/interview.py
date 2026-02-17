from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from jean_claude.errors import JeanClaudeError, LLMError
from jean_claude.llm.base import LLMClient
from jean_claude.prefs.profile import missing_profile_fields, normalize_user_profile, summarize_profile
from jean_claude.prefs.store import PreferencesStore
from jean_claude.prompts import build_extraction_system_prompt, build_extraction_user_prompt


_FIRST_QUESTION = "Tell me 2-3 movies or series you loved recently, and why you liked them."

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


@dataclass(slots=True)
class InterviewUpdate:
    profile: dict[str, Any]
    done: bool
    next_question: str
    missing_fields: list[str]


def run_interview(
    *,
    client: LLMClient,
    model: str,
    store: PreferencesStore,
    max_turns: int = 8,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
) -> dict[str, Any]:
    profile = store.load()

    output_fn("Jean-Claude: Let us tune your taste profile.")
    output_fn("Jean-Claude: Commands: /summary, /done, /skip")

    question = _FIRST_QUESTION
    turns = 0

    while turns < max_turns:
        output_fn(f"\nJean-Claude: {question}")
        user_message = input_fn("You: ").strip()
        if not user_message:
            output_fn("Jean-Claude: I did not catch that. Give me a short answer, or type /skip.")
            continue

        command = user_message.casefold()
        if command in {"/summary", "/show"}:
            _print_summary(profile, output_fn)
            continue
        if command in {"/done", "/finish"}:
            break
        if command == "/skip":
            question = _fallback_question(missing_profile_fields(profile))
            turns += 1
            continue

        try:
            update = _extract_update(client=client, model=model, current_profile=profile, latest_user_message=user_message)
        except LLMError as exc:
            raise JeanClaudeError(f"Interview extraction failed: {exc}") from exc

        profile = update.profile
        store.save(profile)
        turns += 1

        if update.done:
            break

        question = update.next_question or _fallback_question(update.missing_fields)

    _print_summary(profile, output_fn)
    confirmation = input_fn("Jean-Claude: Did I get this right? [Y/n]: ").strip().casefold()
    if confirmation in {"", "y", "yes"}:
        output_fn("Jean-Claude: Great. I saved your baseline preferences.")
    else:
        output_fn("Jean-Claude: Got it. You can run the interview again to refine your profile.")

    store.save(profile)
    return profile


def _extract_update(*, client: LLMClient, model: str, current_profile: dict[str, Any], latest_user_message: str) -> InterviewUpdate:
    system_prompt = build_extraction_system_prompt()
    user_prompt = build_extraction_user_prompt(current_profile=current_profile, latest_user_message=latest_user_message)
    result = client.complete(user_prompt, model=model, system_prompt=system_prompt)
    payload = _parse_json_payload(result.text)
    if not isinstance(payload, dict):
        raise LLMError("Extractor did not return a JSON object")

    next_profile = normalize_user_profile(payload.get("profile") if isinstance(payload.get("profile"), dict) else current_profile)

    missing = payload.get("missing_fields")
    if isinstance(missing, list):
        missing_fields = [str(item) for item in missing if isinstance(item, (str, int, float))]
    else:
        missing_fields = missing_profile_fields(next_profile)

    done_value = payload.get("done")
    done = bool(done_value)
    if len(missing_profile_fields(next_profile)) <= 1:
        done = True

    next_question_value = payload.get("next_question")
    next_question = next_question_value.strip() if isinstance(next_question_value, str) else ""
    if not next_question:
        next_question = _fallback_question(missing_fields)

    return InterviewUpdate(
        profile=next_profile,
        done=done,
        next_question=next_question,
        missing_fields=missing_fields,
    )


def _parse_json_payload(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        raise LLMError("Model returned empty output")

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            candidate = "\n".join(lines[1:-1]).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = stripped[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise LLMError("Model output is not valid JSON")


def _fallback_question(missing_fields: list[str]) -> str:
    if not missing_fields:
        return "Any final preference or hard no-go before I save this profile?"
    target = missing_fields[0]
    if target == "genres_like":
        return "Which genres do you usually enjoy most?"
    if target == "languages":
        return "Which languages are you comfortable watching in?"
    if target == "subtitles":
        return "Do you prefer subtitles, dubbed audio, or no preference?"
    if target == "recency":
        return "Do you want mostly new releases, classics, or a mix?"
    if target == "movie_vs_series":
        return "Do you prefer movies, series, or both?"
    if target == "episode_commitment":
        return "For series, do you prefer short, medium, or long commitments?"
    if target == "examples":
        return "Can you share one title you loved and one you did not?"
    return "What is one important preference I should know before recommending titles?"


def _print_summary(profile: dict[str, Any], output_fn: OutputFn) -> None:
    output_fn("\nJean-Claude: Here is what I understood:")
    for line in summarize_profile(profile):
        output_fn(f"- {line}")
