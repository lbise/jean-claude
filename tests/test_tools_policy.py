from __future__ import annotations

import unittest

from jean_claude.tools import BashPolicy, ToolSettings


class ToolsPolicyTestCase(unittest.TestCase):
    def test_unrestricted_mode_uses_shell_command_plan(self) -> None:
        policy = BashPolicy(ToolSettings(execution_policy="unrestricted", bash_allowlist=["echo"]))
        plan = policy.plan(command="ls -la ~")
        self.assertEqual(plan.mode, "unrestricted")
        self.assertEqual(plan.shell_command, "ls -la ~")

    def test_allowlist_mode_parses_argv_plan(self) -> None:
        policy = BashPolicy(ToolSettings(execution_policy="allowlist", bash_allowlist=["ls"]))
        plan = policy.plan(command="ls -la")
        self.assertEqual(plan.mode, "allowlist")
        self.assertEqual(plan.argv, ["ls", "-la"])


if __name__ == "__main__":
    unittest.main()
