from __future__ import annotations

import unittest

from jean_claude.conversation import ConversationEngine
from jean_claude.conversation.engine import ONBOARDING_MODE, OPEN_CHAT_MODE
from jean_claude.llm.mock import MockLLMClient


class ConversationEngineTestCase(unittest.TestCase):
    def test_onboarding_start_generates_first_question(self) -> None:
        engine = ConversationEngine(
            client=MockLLMClient(),
            model="mock-v1",
            mode=ONBOARDING_MODE,
            initial_state={"profile": {}},
        )

        turn = engine.start()
        self.assertIn("Great", turn.assistant_message)
        self.assertIn("Tell me", turn.next_question)

    def test_onboarding_reply_updates_profile_state(self) -> None:
        engine = ConversationEngine(
            client=MockLLMClient(),
            model="mock-v1",
            mode=ONBOARDING_MODE,
            initial_state={"profile": {}},
        )
        engine.start()
        turn = engine.reply("I like sci-fi movies in English with subtitles")
        profile = turn.state["profile"]
        self.assertIn("sci-fi", profile["genres_like"])
        self.assertIn("english", profile["languages"])
        self.assertEqual(profile["subtitles"], "prefer_subtitles")

    def test_open_chat_mode_returns_assistant_message(self) -> None:
        engine = ConversationEngine(
            client=MockLLMClient(),
            model="mock-v1",
            mode=OPEN_CHAT_MODE,
            initial_state={"profile": {}},
        )
        engine.start()
        turn = engine.reply("Recommend me a tense thriller")
        self.assertIn("That makes sense", turn.assistant_message)


if __name__ == "__main__":
    unittest.main()
