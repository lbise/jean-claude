from __future__ import annotations

import unittest

from jean_claude.prompts import PromptPackRepository


class PromptPackLayoutTestCase(unittest.TestCase):
    def test_chat_flow_references_yaml_state_machine(self) -> None:
        repo = PromptPackRepository()
        flow = repo.load_flow("chat")
        active = flow.states["active"]
        self.assertTrue(active.output_schema_path.endswith("turn.chat.json"))
        self.assertIn("bash.run", active.tools)
        self.assertGreater(len(active.transitions), 0)

    def test_chat_flow_uses_mode_prompt_file(self) -> None:
        repo = PromptPackRepository()
        flow = repo.load_flow("chat")
        mode_prompt = repo.read_text(flow.mode_prompt)
        self.assertIn("Mode: Open Chat", mode_prompt)


if __name__ == "__main__":
    unittest.main()
