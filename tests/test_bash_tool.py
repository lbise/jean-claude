from __future__ import annotations

import unittest

from jean_claude.errors import ToolError
from jean_claude.tools import BashPolicy, BashRunTool, ToolContext, ToolSettings


class BashToolTestCase(unittest.TestCase):
    def test_allowlist_executes_allowed_command(self) -> None:
        policy = BashPolicy(ToolSettings(execution_policy="allowlist", bash_allowlist=["echo"]))
        tool = BashRunTool(policy=policy)
        result = tool.run({"command": "echo hello"}, ToolContext())
        self.assertTrue(result.ok)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hello", result.output)

    def test_allowlist_blocks_unlisted_command(self) -> None:
        policy = BashPolicy(ToolSettings(execution_policy="allowlist", bash_allowlist=["echo"]))
        tool = BashRunTool(policy=policy)
        with self.assertRaises(ToolError):
            tool.run({"command": "ls"}, ToolContext())


if __name__ == "__main__":
    unittest.main()
