from __future__ import annotations

import json
import re
from typing import Any

from jean_claude.llm.base import LLMResult
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
    ) -> LLMResult:
        selected_model = model or self.default_model

        if system_prompt and "structured extraction mode" in system_prompt.casefold():
            text = self._mock_extraction_response(prompt)
            return LLMResult(
                provider=self.provider_name,
                model=selected_model,
                text=text,
                usage={"input_tokens": 0, "output_tokens": 0},
                raw={"source": "mock", "mode": "extraction"},
            )

        prefix = "Mock recommendation"
        if system_prompt:
            prefix = f"{prefix} ({system_prompt[:40]})"
        text = f"{prefix}: based on your input, consider '{prompt[:80]}'."
        return LLMResult(
            provider=self.provider_name,
            model=selected_model,
            text=text,
            usage={"input_tokens": 0, "output_tokens": 0},
            raw={"source": "mock"},
        )

    def _mock_extraction_response(self, prompt: str) -> str:
        current_profile = self._extract_profile_json(prompt)
        profile = normalize_user_profile(current_profile)
        user_message = self._extract_latest_message(prompt)
        lowered = user_message.casefold()

        _merge_terms(profile["genres_like"], _detect_positive_genres(lowered))
        _merge_terms(profile["genres_avoid"], _detect_avoided_genres(lowered))
        _merge_terms(profile["languages"], _detect_languages(lowered))

        if "subtitle" in lowered:
            profile["subtitles"] = "prefer_subtitles"
        if "dub" in lowered:
            profile["subtitles"] = "prefer_dubbed"

        if "new" in lowered or "recent" in lowered:
            profile["recency"] = "new_releases"
        elif "classic" in lowered or "old" in lowered:
            profile["recency"] = "classics"
        elif "mix" in lowered or "both" in lowered:
            profile["recency"] = "mixed"

        if "movies" in lowered and "series" in lowered:
            profile["movie_vs_series"] = "both"
        elif "series" in lowered or "show" in lowered:
            profile["movie_vs_series"] = "series"
        elif "movie" in lowered or "film" in lowered:
            profile["movie_vs_series"] = "movies"

        if "short" in lowered:
            profile["episode_commitment"] = "short"
        elif "long" in lowered:
            profile["episode_commitment"] = "long"
        elif "medium" in lowered:
            profile["episode_commitment"] = "medium"

        quoted_titles = re.findall(r"'([^']+)'|\"([^\"]+)\"", user_message)
        titles = [first or second for first, second in quoted_titles]
        _merge_terms(profile["favorite_titles"], [title.strip() for title in titles if title.strip()])

        missing = missing_profile_fields(profile)
        done = len(missing) <= 1
        next_question = "Any final preference or hard no-go before I save this profile?"
        if missing:
            target = missing[0]
            next_question = f"I still need '{target}'. Could you share a quick preference there?"

        confidence = {
            "genres_like": 0.9 if profile["genres_like"] else 0.2,
            "genres_avoid": 0.9 if profile["genres_avoid"] else 0.4,
            "favorite_titles": 0.8 if profile["favorite_titles"] else 0.3,
            "disliked_titles": 0.6 if profile["disliked_titles"] else 0.3,
            "tone_like": 0.6 if profile["tone_like"] else 0.3,
            "tone_avoid": 0.6 if profile["tone_avoid"] else 0.3,
            "languages": 0.9 if profile["languages"] else 0.3,
            "subtitles": 0.8 if profile["subtitles"] != "unknown" else 0.3,
            "recency": 0.8 if profile["recency"] != "unknown" else 0.3,
            "release_year_min": 0.5 if profile["release_year_min"] else 0.2,
            "release_year_max": 0.5 if profile["release_year_max"] else 0.2,
            "content_limits": 0.7 if profile["content_limits"] else 0.3,
            "movie_vs_series": 0.8 if profile["movie_vs_series"] != "unknown" else 0.3,
            "episode_commitment": 0.8 if profile["episode_commitment"] != "unknown" else 0.3,
        }

        payload = {
            "profile": profile,
            "updated_fields": [],
            "missing_fields": missing,
            "confidence_by_field": confidence,
            "done": done,
            "next_question": next_question,
            "notes": ["mock extraction"],
        }
        return json.dumps(payload)

    def _extract_profile_json(self, prompt: str) -> dict[str, Any]:
        marker_start = "Current profile JSON:"
        marker_end = "Latest user message:"
        start = prompt.find(marker_start)
        end = prompt.find(marker_end)
        if start == -1 or end == -1 or end <= start:
            return {}
        body = prompt[start + len(marker_start) : end].strip()
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _extract_latest_message(self, prompt: str) -> str:
        marker = "Latest user message:"
        idx = prompt.find(marker)
        if idx == -1:
            return ""
        return prompt[idx + len(marker) :].strip()


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
