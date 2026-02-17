from __future__ import annotations

import unittest

from jean_claude.prompts import PromptPackRepository, default_base_instructions


class PromptRepositoryTestCase(unittest.TestCase):
    def test_base_prompts_load_from_filesystem_pack(self) -> None:
        repo = PromptPackRepository()
        text = repo.read_text("base/jeanclaude.md")
        self.assertIn("Jean-Claude", text)
        self.assertIn("Personality", text)

    def test_flow_loading_by_mode(self) -> None:
        repo = PromptPackRepository()
        flow = repo.load_flow("open_chat")
        self.assertEqual(flow.mode, "open_chat")
        self.assertEqual(flow.initial_state, "active")
        self.assertIn("active", flow.states)

    def test_default_base_instructions_stacks_two_layers(self) -> None:
        instructions = default_base_instructions()
        self.assertIn("Core Personality", instructions)
        self.assertIn("Global Policies", instructions)


if __name__ == "__main__":
    unittest.main()
