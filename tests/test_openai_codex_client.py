from __future__ import annotations

import unittest

from jean_claude.auth.store import AuthStore
from jean_claude.llm.openai_codex import DEFAULT_INSTRUCTIONS, OpenAICodexClient


class OpenAICodexClientBodyTestCase(unittest.TestCase):
    def test_request_body_has_default_instructions(self) -> None:
        client = OpenAICodexClient(store=AuthStore())
        body = client._build_request_body(model="gpt-5.3-codex", prompt="hello", system_prompt=None)
        self.assertEqual(body["instructions"], DEFAULT_INSTRUCTIONS)

    def test_request_body_uses_custom_system_prompt(self) -> None:
        client = OpenAICodexClient(store=AuthStore())
        body = client._build_request_body(model="gpt-5.3-codex", prompt="hello", system_prompt="custom")
        self.assertEqual(body["instructions"], "custom")


if __name__ == "__main__":
    unittest.main()
