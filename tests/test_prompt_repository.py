from __future__ import annotations

import unittest

from jean_claude.prompts import PromptPackRepository


class PromptRepositoryTestCase(unittest.TestCase):
    def test_base_prompts_load_from_filesystem_pack(self) -> None:
        repo = PromptPackRepository()
        text = repo.read_text("base/jeanclaude.md")
        self.assertIn("Jean-Claude", text)
        self.assertIn("Personality", text)

    def test_flow_loading_by_mode(self) -> None:
        repo = PromptPackRepository()
        flow = repo.load_flow("chat")
        self.assertEqual(flow.mode, "chat")
        self.assertEqual(flow.initial_state, "active")
        self.assertIn("active", flow.states)
        self.assertEqual(flow.tools_catalog, "tools/catalog.yaml")

    def test_load_tools_filters_by_mode(self) -> None:
        repo = PromptPackRepository()
        tools = repo.load_tools("tools/catalog.yaml", mode="chat")
        self.assertGreaterEqual(len(tools), 1)
        self.assertEqual(tools[0].id, "bash.run")


if __name__ == "__main__":
    unittest.main()
