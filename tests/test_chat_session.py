from __future__ import annotations

import unittest

from jean_claude.chat import ChatSession
from jean_claude.llm.mock import MockLLMClient


class ChatSessionTestCase(unittest.TestCase):
    def test_chat_session_returns_response_and_tracks_history(self) -> None:
        session = ChatSession(
            client=MockLLMClient(),
            model="mock-v1",
            profile_context={"genres_like": ["sci-fi"]},
            history_turn_limit=4,
        )

        response = session.ask("I like cerebral sci-fi movies")
        self.assertIn("That makes sense", response)
        self.assertEqual(len(session.messages), 3)
        self.assertEqual(session.messages[0].role, "assistant")
        self.assertEqual(session.messages[1].role, "user")
        self.assertEqual(session.messages[2].role, "assistant")


if __name__ == "__main__":
    unittest.main()
