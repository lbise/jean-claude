from __future__ import annotations

import unittest

from jean_claude.agent import AgentOrchestrator
from jean_claude.llm.mock import MockLLMClient
from jean_claude.prompts import PromptPackRepository
from jean_claude.tools import BashPolicy, BashRunTool, ToolRegistry, ToolSettings


class AgentOrchestratorTestCase(unittest.TestCase):
    def test_orchestrator_can_trigger_bash_tool(self) -> None:
        registry = ToolRegistry()
        policy = BashPolicy(ToolSettings(execution_policy="allowlist", bash_allowlist=["ls"]))
        registry.register(BashRunTool(policy=policy))

        orchestrator = AgentOrchestrator(
            llm_client=MockLLMClient(),
            model="mock-v1",
            mode="chat",
            prompt_repository=PromptPackRepository(),
            tool_registry=registry,
        )

        result = orchestrator.handle_user_message("list files in your home directory")
        self.assertIn("Tool results:", result.assistant_message)
        self.assertGreaterEqual(len(result.tool_results), 1)
        self.assertEqual(result.tool_results[0]["tool"], "bash.run")


if __name__ == "__main__":
    unittest.main()
