# Jean-Claude Prompt Pack (v1)

This document describes the first prompt pack used to drive Jean-Claude behavior.

Source of truth:

- `src/jean_claude/prompts/v1.py`

## Prompt layers

- `CORE_SYSTEM_PROMPT`
  - Shared identity and behavior constraints.
- `INTERVIEW_SYSTEM_PROMPT`
  - Rules for interactive preference discovery.
- `build_extraction_system_prompt()`
  - Structured extraction instructions and output schema.
- `RECOMMENDER_SYSTEM_PROMPT`
  - Rules for ranking candidates.
- `build_recommender_system_prompt()`
  - Recommender instructions plus strict output schema.

## Schemas

- `USER_PREFERENCE_SCHEMA`
  - Canonical profile shape.
- `EXTRACTION_OUTPUT_SCHEMA`
  - Expected extractor output shape.
- `RECOMMENDATION_OUTPUT_SCHEMA`
  - Expected recommendation output shape.

## Intended flow

1. Interview mode asks one question per turn.
2. Extraction mode converts the latest user message into structured profile updates.
3. Recommendation mode ranks a candidate set and explains the fit.

## Example usage (Python)

```python
from jean_claude.prompts import (
    build_extraction_system_prompt,
    build_extraction_user_prompt,
    build_recommender_system_prompt,
    build_recommender_user_prompt,
)

extract_system = build_extraction_system_prompt()
extract_user = build_extraction_user_prompt(
    current_profile={"genres_like": [], "genres_avoid": []},
    latest_user_message="I loved Arrival and Dune, but I dislike jump scares.",
)

recommend_system = build_recommender_system_prompt()
recommend_user = build_recommender_user_prompt(
    user_profile={"genres_like": ["sci-fi"]},
    candidates=[{"id": "movie_1", "title": "Blade Runner 2049", "media_type": "movie"}],
    top_n=5,
)
```
