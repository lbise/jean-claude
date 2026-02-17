from __future__ import annotations

import unittest

from jean_claude.prompts.v1 import (
    CORE_SYSTEM_PROMPT,
    EXTRACTION_OUTPUT_SCHEMA,
    INTERVIEW_SYSTEM_PROMPT,
    RECOMMENDATION_OUTPUT_SCHEMA,
    RECOMMENDER_SYSTEM_PROMPT,
    USER_PREFERENCE_SCHEMA,
    build_extraction_system_prompt,
    build_recommender_system_prompt,
)


class PromptPackV1TestCase(unittest.TestCase):
    def test_core_prompt_mentions_agent_identity(self) -> None:
        self.assertIn("Jean-Claude", CORE_SYSTEM_PROMPT)
        self.assertIn("TV series", CORE_SYSTEM_PROMPT)

    def test_interview_prompt_enforces_single_question(self) -> None:
        self.assertIn("Ask exactly one question per turn", INTERVIEW_SYSTEM_PROMPT)

    def test_user_preference_schema_has_required_fields(self) -> None:
        required = USER_PREFERENCE_SCHEMA["required"]
        self.assertIn("genres_like", required)
        self.assertIn("content_limits", required)

    def test_extraction_schema_has_profile_and_done(self) -> None:
        required = EXTRACTION_OUTPUT_SCHEMA["required"]
        self.assertIn("profile", required)
        self.assertIn("done", required)

    def test_recommender_schema_has_recommendations(self) -> None:
        required = RECOMMENDATION_OUTPUT_SCHEMA["required"]
        self.assertEqual(required, ["recommendations"])

    def test_built_system_prompts_include_schema_instruction(self) -> None:
        extraction_prompt = build_extraction_system_prompt()
        recommender_prompt = build_recommender_system_prompt()
        self.assertIn("Must validate against this JSON schema", extraction_prompt)
        self.assertIn("Must validate against this JSON schema", recommender_prompt)
        self.assertIn("strict JSON", RECOMMENDER_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
