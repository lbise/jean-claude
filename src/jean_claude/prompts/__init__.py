"""Prompt packs for Jean-Claude."""

from .v1 import (
    CORE_SYSTEM_PROMPT,
    EXTRACTION_OUTPUT_SCHEMA,
    INTERVIEW_SYSTEM_PROMPT,
    RECOMMENDATION_OUTPUT_SCHEMA,
    RECOMMENDER_SYSTEM_PROMPT,
    USER_PREFERENCE_SCHEMA,
    build_extraction_system_prompt,
    build_extraction_user_prompt,
    build_recommender_system_prompt,
    build_recommender_user_prompt,
)

__all__ = [
    "CORE_SYSTEM_PROMPT",
    "EXTRACTION_OUTPUT_SCHEMA",
    "INTERVIEW_SYSTEM_PROMPT",
    "RECOMMENDATION_OUTPUT_SCHEMA",
    "RECOMMENDER_SYSTEM_PROMPT",
    "USER_PREFERENCE_SCHEMA",
    "build_extraction_system_prompt",
    "build_extraction_user_prompt",
    "build_recommender_system_prompt",
    "build_recommender_user_prompt",
]
