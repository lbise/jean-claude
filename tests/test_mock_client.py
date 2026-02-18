from __future__ import annotations

import unittest

from jean_claude.llm.mock import MockLLMClient


class MockClientTestCase(unittest.TestCase):
    def test_mock_client_returns_text(self) -> None:
        client = MockLLMClient()
        result = client.complete("hello")
        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.model, "mock-v1")
        self.assertIn("Mock response", result.text)


if __name__ == "__main__":
    unittest.main()
