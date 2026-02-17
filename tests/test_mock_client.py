from __future__ import annotations

import unittest

from jean_claude.llm.mock import MockLLMClient


class MockClientTestCase(unittest.TestCase):
    def test_mock_client_returns_text(self) -> None:
        client = MockLLMClient()
        result = client.complete("Suggest a fantasy movie")
        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.model, "mock-v1")
        self.assertIn("Suggest a fantasy movie", result.text)


if __name__ == "__main__":
    unittest.main()
