from __future__ import annotations

from typing import Any


_LIST_FIELDS = {
    "genres_like",
    "genres_avoid",
    "favorite_titles",
    "disliked_titles",
    "tone_like",
    "tone_avoid",
    "languages",
    "content_limits",
}

_STRING_ENUMS = {
    "subtitles": {"prefer_subtitles", "prefer_dubbed", "no_preference", "unknown"},
    "recency": {"new_releases", "mixed", "classics", "unknown"},
    "movie_vs_series": {"movies", "series", "both", "unknown"},
    "episode_commitment": {"short", "medium", "long", "unknown"},
}


def default_user_profile() -> dict[str, Any]:
    return {
        "genres_like": [],
        "genres_avoid": [],
        "favorite_titles": [],
        "disliked_titles": [],
        "tone_like": [],
        "tone_avoid": [],
        "languages": [],
        "subtitles": "unknown",
        "recency": "unknown",
        "release_year_min": None,
        "release_year_max": None,
        "content_limits": [],
        "movie_vs_series": "unknown",
        "episode_commitment": "unknown",
    }


def normalize_user_profile(raw: dict[str, Any] | None) -> dict[str, Any]:
    profile = default_user_profile()
    if not isinstance(raw, dict):
        return profile

    for field_name in _LIST_FIELDS:
        profile[field_name] = _normalize_string_list(raw.get(field_name))

    for field_name, allowed_values in _STRING_ENUMS.items():
        value = raw.get(field_name)
        if isinstance(value, str) and value in allowed_values:
            profile[field_name] = value

    profile["release_year_min"] = _normalize_year(raw.get("release_year_min"))
    profile["release_year_max"] = _normalize_year(raw.get("release_year_max"))
    if (
        isinstance(profile["release_year_min"], int)
        and isinstance(profile["release_year_max"], int)
        and profile["release_year_min"] > profile["release_year_max"]
    ):
        profile["release_year_min"], profile["release_year_max"] = (
            profile["release_year_max"],
            profile["release_year_min"],
        )

    return profile


def summarize_profile(profile: dict[str, Any]) -> list[str]:
    normalized = normalize_user_profile(profile)
    lines = [
        _format_list_line("Likes", normalized["genres_like"]),
        _format_list_line("Avoids", normalized["genres_avoid"]),
        _format_list_line("Favorite titles", normalized["favorite_titles"]),
        _format_list_line("Disliked titles", normalized["disliked_titles"]),
        _format_list_line("Preferred tone", normalized["tone_like"]),
        _format_list_line("Avoided tone", normalized["tone_avoid"]),
        _format_list_line("Languages", normalized["languages"]),
        f"Subtitles: {normalized['subtitles']}",
        f"Recency: {normalized['recency']}",
        f"Movie vs series: {normalized['movie_vs_series']}",
        f"Episode commitment: {normalized['episode_commitment']}",
        _format_year_line(normalized["release_year_min"], normalized["release_year_max"]),
        _format_list_line("Content limits", normalized["content_limits"]),
    ]
    return lines


def missing_profile_fields(profile: dict[str, Any]) -> list[str]:
    normalized = normalize_user_profile(profile)
    missing: list[str] = []

    for field_name in ("genres_like", "languages"):
        if not normalized[field_name]:
            missing.append(field_name)

    for field_name in ("subtitles", "recency", "movie_vs_series", "episode_commitment"):
        if normalized[field_name] == "unknown":
            missing.append(field_name)

    if not normalized["favorite_titles"] and not normalized["disliked_titles"]:
        missing.append("examples")

    return missing


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        return [part for part in parts if part]
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        part = item.strip()
        if not part:
            continue
        key = part.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(part)
    return cleaned


def _normalize_year(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if not text.isdigit():
            return None
        year = int(text)
    elif isinstance(value, int):
        year = value
    else:
        return None

    if year < 1900 or year > 2100:
        return None
    return year


def _format_list_line(label: str, values: list[str]) -> str:
    if not values:
        return f"{label}: unknown"
    return f"{label}: {', '.join(values)}"


def _format_year_line(year_min: int | None, year_max: int | None) -> str:
    if year_min is None and year_max is None:
        return "Release years: unknown"
    if year_min is not None and year_max is not None:
        return f"Release years: {year_min}-{year_max}"
    if year_min is not None:
        return f"Release years: from {year_min}"
    return f"Release years: up to {year_max}"
