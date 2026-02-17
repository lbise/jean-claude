from __future__ import annotations

import json
from typing import Any

from jean_claude.llm.base import DebugHook, LLMResult
from jean_claude.prefs.profile import missing_profile_fields, normalize_user_profile


class MockLLMClient:
    provider_name = "mock"
    default_model = "mock-v1"

    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        debug_hook: DebugHook | None = None,
    ) -> LLMResult:
        selected_model = model or self.default_model
        mode = _detect_mode(system_prompt)
        _emit_debug(
            debug_hook,
            {
                "type": "llm.complete.request",
                "provider": self.provider_name,
                "model": selected_model,
                "system_prompt": system_prompt or "",
                "prompt": prompt,
                "mock_mode": mode,
            },
        )

        if mode == "onboarding_interview":
            payload = self._mock_onboarding_turn(prompt)
            result = LLMResult(
                provider=self.provider_name,
                model=selected_model,
                text=json.dumps(payload),
                usage={"input_tokens": 0, "output_tokens": 0},
                raw={"source": "mock", "mode": "onboarding_interview"},
            )
            _emit_debug(
                debug_hook,
                {
                    "type": "llm.complete.response",
                    "provider": self.provider_name,
                    "model": selected_model,
                    "text": result.text,
                    "usage": result.usage,
                    "raw": result.raw,
                },
            )
            return result

        if mode == "open_chat":
            payload = self._mock_open_chat_turn(prompt)
            result = LLMResult(
                provider=self.provider_name,
                model=selected_model,
                text=json.dumps(payload),
                usage={"input_tokens": 0, "output_tokens": 0},
                raw={"source": "mock", "mode": "open_chat"},
            )
            _emit_debug(
                debug_hook,
                {
                    "type": "llm.complete.response",
                    "provider": self.provider_name,
                    "model": selected_model,
                    "text": result.text,
                    "usage": result.usage,
                    "raw": result.raw,
                },
            )
            return result

        prefix = "Mock recommendation"
        if system_prompt:
            prefix = f"{prefix} ({system_prompt[:40]})"
        text = f"{prefix}: based on your input, consider '{prompt[:80]}'."
        result = LLMResult(
            provider=self.provider_name,
            model=selected_model,
            text=text,
            usage={"input_tokens": 0, "output_tokens": 0},
            raw={"source": "mock"},
        )
        _emit_debug(
            debug_hook,
            {
                "type": "llm.complete.response",
                "provider": self.provider_name,
                "model": selected_model,
                "text": result.text,
                "usage": result.usage,
                "raw": result.raw,
            },
        )
        return result

    def _mock_onboarding_turn(self, prompt: str) -> dict[str, Any]:
        context = _parse_prompt_context(prompt)
        event = _as_text(context["flow_context"].get("event"))
        current_profile = normalize_user_profile(context["profile"])

        if event == "session_start":
            return {
                "assistant_message": "Great, I will learn your taste step by step.",
                "next_question": "Tell me 2-3 movies or series you loved recently, and why you liked them.",
                "profile_patch": {},
                "done": False,
                "notes": ["mock onboarding start"],
            }

        user_message = context["latest_user_message"]
        updated_profile = _infer_profile_from_text(current_profile, user_message)
        patch = _profile_patch(current_profile, updated_profile)
        missing = missing_profile_fields(updated_profile)
        done = len(missing) <= 1

        next_question = "Any final preference or hard no-go before I save this profile?"
        if not done:
            next_question = _fallback_question(missing)

        return {
            "assistant_message": "Got it, that gives me a clearer picture of your taste.",
            "next_question": next_question,
            "profile_patch": patch,
            "done": done,
            "notes": ["mock onboarding turn"],
        }

    def _mock_open_chat_turn(self, prompt: str) -> dict[str, Any]:
        context = _parse_prompt_context(prompt)
        event = _as_text(context["flow_context"].get("event"))
        current_profile = normalize_user_profile(context["profile"])

        if event == "session_start":
            return {
                "assistant_message": "Hi, I am ready to talk movies and series whenever you want.",
                "next_question": "",
                "profile_patch": {},
                "done": False,
                "notes": ["mock chat start"],
            }

        user_message = context["latest_user_message"]
        updated_profile = _infer_profile_from_text(current_profile, user_message)
        patch = _profile_patch(current_profile, updated_profile)
        next_question = ""

        if "recommend" in user_message.casefold() and not updated_profile.get("genres_like"):
            next_question = "What genres are you in the mood for right now?"

        return {
            "assistant_message": f"That makes sense. Based on that, I would focus on similar titles with that vibe: {user_message[:120]}",
            "next_question": next_question,
            "profile_patch": patch,
            "done": False,
            "notes": ["mock chat turn"],
        }


def _detect_mode(system_prompt: str | None) -> str:
    prompt = system_prompt.casefold() if isinstance(system_prompt, str) else ""
    if "mode: onboarding interview" in prompt:
        return "onboarding_interview"
    if "mode: open chat" in prompt:
        return "open_chat"
    return "generic"


def _parse_prompt_context(prompt: str) -> dict[str, Any]:
    profile = _parse_json_block(prompt, "USER_PROFILE_JSON")
    flow_context = _parse_json_block(prompt, "FLOW_CONTEXT_JSON")
    latest_message = _parse_text_block(prompt, "LATEST_USER_MESSAGE")
    return {
        "profile": profile if isinstance(profile, dict) else {},
        "flow_context": flow_context if isinstance(flow_context, dict) else {},
        "latest_user_message": latest_message,
    }


def _parse_json_block(prompt: str, marker: str) -> dict[str, Any] | list[Any] | None:
    content = _extract_block(prompt, marker)
    if content is None:
        return None
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    if isinstance(data, (dict, list)):
        return data
    return None


def _parse_text_block(prompt: str, marker: str) -> str:
    content = _extract_block(prompt, marker)
    if content is None:
        return ""
    return content.strip()


def _extract_block(prompt: str, marker: str) -> str | None:
    start_tag = f"[{marker}]"
    end_tag = f"[/{marker}]"
    start = prompt.find(start_tag)
    if start == -1:
        return None
    end = prompt.find(end_tag, start + len(start_tag))
    if end == -1:
        return None
    return prompt[start + len(start_tag) : end].strip()


def _as_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _infer_profile_from_text(profile: dict[str, Any], user_message: str) -> dict[str, Any]:
    updated = normalize_user_profile(profile)
    text = user_message.casefold()

    _merge_terms(updated["genres_like"], _detect_positive_genres(text))
    _merge_terms(updated["genres_avoid"], _detect_avoided_genres(text))
    _merge_terms(updated["languages"], _detect_languages(text))

    if "subtitle" in text:
        updated["subtitles"] = "prefer_subtitles"
    if "dub" in text:
        updated["subtitles"] = "prefer_dubbed"

    if "new" in text or "recent" in text:
        updated["recency"] = "new_releases"
    elif "classic" in text or "old" in text:
        updated["recency"] = "classics"
    elif "mix" in text or "both" in text:
        updated["recency"] = "mixed"

    if "movies" in text and "series" in text:
        updated["movie_vs_series"] = "both"
    elif "series" in text or "show" in text:
        updated["movie_vs_series"] = "series"
    elif "movie" in text or "film" in text:
        updated["movie_vs_series"] = "movies"

    if "short" in text:
        updated["episode_commitment"] = "short"
    elif "long" in text:
        updated["episode_commitment"] = "long"
    elif "medium" in text:
        updated["episode_commitment"] = "medium"

    return updated


def _profile_patch(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    for key, value in after.items():
        if before.get(key) != value:
            patch[key] = value
    return patch


def _merge_terms(target: list[str], additions: list[str]) -> None:
    seen = {value.casefold() for value in target}
    for value in additions:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        target.append(value)


def _detect_positive_genres(text: str) -> list[str]:
    genres = []
    for genre in ("sci-fi", "science fiction", "thriller", "drama", "comedy", "fantasy", "crime", "romance"):
        if genre in text:
            genres.append("sci-fi" if genre == "science fiction" else genre)
    return genres


def _detect_avoided_genres(text: str) -> list[str]:
    avoided = []
    negative = any(token in text for token in ("avoid", "dislike", "hate", "no "))
    for genre in ("horror", "gore", "slasher"):
        if genre in text and negative:
            avoided.append(genre)
    return avoided


def _detect_languages(text: str) -> list[str]:
    languages = []
    for language in ("english", "french", "spanish", "japanese", "korean", "german", "italian"):
        if language in text:
            languages.append(language)
    return languages


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


def _emit_debug(debug_hook: DebugHook | None, payload: dict[str, Any]) -> None:
    if debug_hook is not None:
        debug_hook(payload)
