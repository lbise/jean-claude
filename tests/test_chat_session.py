from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from jean_claude.chat import ChatSession
from jean_claude.llm.base import LLMResult


class RecordingLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, str]] = []

    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        debug_hook=None,
    ) -> LLMResult:
        self.calls.append(
            {
                "model": model or "",
                "prompt": prompt,
                "system_prompt": system_prompt or "",
            }
        )
        return LLMResult(provider="recording", model=model or "recording-v1", text=self.responses.pop(0))


class ChatSessionTestCase(unittest.TestCase):
    def test_chat_session_sends_system_prompt_and_tracks_history(self) -> None:
        client = RecordingLLMClient(["First reply", "Second reply"])

        with TemporaryDirectory() as temp_dir:
            system_prompt_path = Path(temp_dir) / "system.md"
            system_prompt_path.write_text("# Prompt v1\n\nBe helpful.", encoding="utf-8")

            session = ChatSession(
                client=client,
                model="recording-v1",
                system_prompt_path=system_prompt_path,
                history_turn_limit=4,
            )

            first_response = session.ask("Hello there")
            system_prompt_path.write_text("# Prompt v2\n\nBe extra helpful.", encoding="utf-8")
            second_response = session.ask("Can you elaborate?")

        self.assertEqual(first_response, "First reply")
        self.assertEqual(second_response, "Second reply")
        self.assertEqual(len(session.messages), 4)
        self.assertEqual(session.messages[0].role, "user")
        self.assertEqual(session.messages[1].role, "assistant")
        self.assertEqual(client.calls[0]["system_prompt"], "# Prompt v1\n\nBe helpful.")
        self.assertEqual(client.calls[1]["system_prompt"], "# Prompt v2\n\nBe extra helpful.")
        self.assertIn("# Conversation History\n\n(none yet)", client.calls[0]["prompt"])
        self.assertIn("# Latest User Message\n\nHello there", client.calls[0]["prompt"])
        self.assertIn("User: Hello there", client.calls[1]["prompt"])
        self.assertIn("Assistant: First reply", client.calls[1]["prompt"])
        self.assertIn("# Latest User Message\n\nCan you elaborate?", client.calls[1]["prompt"])

    def test_chat_session_expands_markdown_file_references(self) -> None:
        client = RecordingLLMClient(["First reply"])

        with TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            system_prompt_path = base_path / "system.md"
            notes_path = base_path / "notes.md"
            system_prompt_path.write_text("# Prompt\n\nBe helpful.", encoding="utf-8")
            notes_path.write_text("# Notes\n\nUse the latest draft.", encoding="utf-8")

            session = ChatSession(
                client=client,
                model="recording-v1",
                system_prompt_path=system_prompt_path,
            )

            with patch("jean_claude.chat.session.Path.cwd", return_value=base_path):
                response = session.ask("Please review @notes.md, then summarize it.")

        self.assertEqual(response, "First reply")
        self.assertIn("[Included markdown file: notes.md]", client.calls[0]["prompt"])
        self.assertIn("# Notes\n\nUse the latest draft.", client.calls[0]["prompt"])
        self.assertNotIn("Please review @notes.md", client.calls[0]["prompt"])
        self.assertIn("[Included markdown file: notes.md]", session.messages[0].content)

    def test_chat_session_leaves_missing_markdown_reference_unchanged(self) -> None:
        client = RecordingLLMClient(["First reply"])

        with TemporaryDirectory() as temp_dir:
            system_prompt_path = Path(temp_dir) / "system.md"
            system_prompt_path.write_text("# Prompt\n\nBe helpful.", encoding="utf-8")

            session = ChatSession(
                client=client,
                model="recording-v1",
                system_prompt_path=system_prompt_path,
            )

            with patch("jean_claude.chat.session.Path.cwd", return_value=Path(temp_dir)):
                session.ask("Maybe @alias.md is just a handle.")

        self.assertIn("# Latest User Message\n\nMaybe @alias.md is just a handle.", client.calls[0]["prompt"])
        self.assertNotIn("[Included markdown file:", client.calls[0]["prompt"])

    def test_chat_session_expands_multiple_markdown_file_references(self) -> None:
        client = RecordingLLMClient(["First reply"])

        with TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            system_prompt_path = base_path / "system.md"
            first_path = base_path / "one.md"
            second_path = base_path / "two.md"
            system_prompt_path.write_text("# Prompt\n\nBe helpful.", encoding="utf-8")
            first_path.write_text("# One\n\nAlpha", encoding="utf-8")
            second_path.write_text("# Two\n\nBeta", encoding="utf-8")

            session = ChatSession(
                client=client,
                model="recording-v1",
                system_prompt_path=system_prompt_path,
            )

            with patch("jean_claude.chat.session.Path.cwd", return_value=base_path):
                session.ask("Compare @one.md with @two.md.")

        self.assertIn("[Included markdown file: one.md]", client.calls[0]["prompt"])
        self.assertIn("# One\n\nAlpha", client.calls[0]["prompt"])
        self.assertIn("[Included markdown file: two.md]", client.calls[0]["prompt"])
        self.assertIn("# Two\n\nBeta", client.calls[0]["prompt"])


if __name__ == "__main__":
    unittest.main()
