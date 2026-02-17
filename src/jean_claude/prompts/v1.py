from __future__ import annotations

import json
from textwrap import dedent
from typing import Any


CORE_SYSTEM_PROMPT = dedent(
    """
    You are Jean-Claude, a media discovery agent specialized in TV series and movies.

    Mission:
    - Help users discover titles they are likely to enjoy.
    - Be precise about user taste and constraints.
    - Prefer clarity and practical usefulness over long answers.

    Behavior:
    - Be friendly, concise, and direct.
    - Never invent user preferences.
    - If data is missing, ask one focused follow-up question.
    - Respect explicit dislikes and content limits as hard constraints.
    - When uncertain, state uncertainty instead of pretending confidence.
    """
).strip()


INTERVIEW_SYSTEM_PROMPT = dedent(
    """
    Mode: Preference Interview.

    Objective:
    Build a baseline user taste profile for movie and TV recommendations.

    Interview rules:
    - Ask exactly one question per turn.
    - Keep each question short and natural.
    - Prioritize unknown or low-confidence fields.
    - Use examples from the user to infer genres, tone, and constraints.
    - If the user says "skip", mark the field as unknown and continue.
    - Do not ask multiple bundled questions in one turn.

    Completion criteria:
    - End interview when baseline coverage is good enough for first recommendations.
    - Then provide a concise summary of understood preferences.
    - Ask for confirmation: "Did I get this right?"

    Hard constraints:
    - Never pressure the user to answer.
    - Never infer sensitive personal traits.
    - Never overwrite explicit user statements with assumptions.
    """
).strip()


PROFILE_FIELDS = [
    "genres_like",
    "genres_avoid",
    "favorite_titles",
    "disliked_titles",
    "tone_like",
    "tone_avoid",
    "languages",
    "subtitles",
    "recency",
    "release_year_min",
    "release_year_max",
    "content_limits",
    "movie_vs_series",
    "episode_commitment",
]


USER_PREFERENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": PROFILE_FIELDS,
    "properties": {
        "genres_like": {"type": "array", "items": {"type": "string"}},
        "genres_avoid": {"type": "array", "items": {"type": "string"}},
        "favorite_titles": {"type": "array", "items": {"type": "string"}},
        "disliked_titles": {"type": "array", "items": {"type": "string"}},
        "tone_like": {"type": "array", "items": {"type": "string"}},
        "tone_avoid": {"type": "array", "items": {"type": "string"}},
        "languages": {"type": "array", "items": {"type": "string"}},
        "subtitles": {
            "type": "string",
            "enum": ["prefer_subtitles", "prefer_dubbed", "no_preference", "unknown"],
        },
        "recency": {
            "type": "string",
            "enum": ["new_releases", "mixed", "classics", "unknown"],
        },
        "release_year_min": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "release_year_max": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "content_limits": {"type": "array", "items": {"type": "string"}},
        "movie_vs_series": {
            "type": "string",
            "enum": ["movies", "series", "both", "unknown"],
        },
        "episode_commitment": {
            "type": "string",
            "enum": ["short", "medium", "long", "unknown"],
        },
    },
}


EXTRACTION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "profile",
        "updated_fields",
        "missing_fields",
        "confidence_by_field",
        "done",
        "next_question",
        "notes",
    ],
    "properties": {
        "profile": USER_PREFERENCE_SCHEMA,
        "updated_fields": {"type": "array", "items": {"type": "string"}},
        "missing_fields": {"type": "array", "items": {"type": "string"}},
        "confidence_by_field": {
            "type": "object",
            "additionalProperties": False,
            "required": PROFILE_FIELDS,
            "properties": {
                field_name: {"type": "number", "minimum": 0.0, "maximum": 1.0}
                for field_name in PROFILE_FIELDS
            },
        },
        "done": {"type": "boolean"},
        "next_question": {"type": "string"},
        "notes": {"type": "array", "items": {"type": "string"}},
    },
}


RECOMMENDER_SYSTEM_PROMPT = dedent(
    """
    Mode: Recommendation Ranking.

    Objective:
    Rank candidate movies and series against a user preference profile.

    Ranking rules:
    - Treat explicit dislikes and content limits as hard constraints.
    - Prefer candidates that match multiple positive signals.
    - Penalize candidates that conflict with known preferences.
    - If profile data is sparse, keep reasons cautious and specific.

    Output rules:
    - Return strict JSON only, no markdown.
    - Use only fields defined by the output schema.
    - Keep each reason concise and evidence-based.
    """
).strip()


RECOMMENDATION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["recommendations"],
    "properties": {
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "rank",
                    "candidate_id",
                    "title",
                    "media_type",
                    "score",
                    "reason",
                    "matched_signals",
                    "cautions",
                ],
                "properties": {
                    "rank": {"type": "integer", "minimum": 1},
                    "candidate_id": {"type": "string"},
                    "title": {"type": "string"},
                    "media_type": {"type": "string", "enum": ["movie", "series"]},
                    "score": {"type": "number", "minimum": 0, "maximum": 100},
                    "reason": {"type": "string"},
                    "matched_signals": {"type": "array", "items": {"type": "string"}},
                    "cautions": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}


def build_extraction_system_prompt() -> str:
    schema_json = json.dumps(EXTRACTION_OUTPUT_SCHEMA, indent=2, sort_keys=True)
    return dedent(
        f"""
        {CORE_SYSTEM_PROMPT}

        {INTERVIEW_SYSTEM_PROMPT}

        You are now in structured extraction mode.

        Task:
        - Read the current profile and latest user message.
        - Update the profile carefully.
        - Preserve existing values unless the user explicitly changes them.
        - Normalize values to short lowercase labels where appropriate.

        Output contract:
        - Return JSON only.
        - Must validate against this JSON schema:
        {schema_json}
        """
    ).strip()


def build_extraction_user_prompt(*, current_profile: dict[str, Any], latest_user_message: str) -> str:
    profile_json = json.dumps(current_profile, indent=2, sort_keys=True)
    return dedent(
        f"""
        Current profile JSON:
        {profile_json}

        Latest user message:
        {latest_user_message.strip()}
        """
    ).strip()


def build_recommender_system_prompt() -> str:
    schema_json = json.dumps(RECOMMENDATION_OUTPUT_SCHEMA, indent=2, sort_keys=True)
    return dedent(
        f"""
        {CORE_SYSTEM_PROMPT}

        {RECOMMENDER_SYSTEM_PROMPT}

        Output contract:
        - Return JSON only.
        - Must validate against this JSON schema:
        {schema_json}
        """
    ).strip()


def build_recommender_user_prompt(
    *,
    user_profile: dict[str, Any],
    candidates: list[dict[str, Any]],
    top_n: int,
) -> str:
    profile_json = json.dumps(user_profile, indent=2, sort_keys=True)
    candidates_json = json.dumps(candidates, indent=2, sort_keys=True)
    return dedent(
        f"""
        Rank candidates for this user.

        Return exactly the top {top_n} items sorted by descending score.

        User profile:
        {profile_json}

        Candidates:
        {candidates_json}
        """
    ).strip()
