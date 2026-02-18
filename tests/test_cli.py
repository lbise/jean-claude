from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from jean_claude.cli import main


class CLITestCase(unittest.TestCase):
    def test_cli_llm_test_mock_json(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "llm",
                    "test",
                    "--provider",
                    "mock",
                    "--prompt",
                    "Find a thriller",
                    "--json",
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertIn('"provider": "mock"', output.getvalue())

    def test_cli_chat_one_shot(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "chat",
                    "--provider",
                    "mock",
                    "--model",
                    "mock-v1",
                    "--message",
                    "list files in your home directory",
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertIn("Jean-Claude:", output.getvalue())
        self.assertIn("Tool results:", output.getvalue())

    def test_cli_tools_list(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["tools", "list"])
        self.assertEqual(exit_code, 0)
        self.assertIn("bash.run", output.getvalue())

    def test_cli_tools_policy_set_unrestricted_requires_flag(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["tools", "policy", "set", "unrestricted"])
        self.assertEqual(exit_code, 1)
        self.assertIn("yes-i-understand", output.getvalue())

    def test_cli_tools_policy_set_and_show(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_dir = Path(tmp)
            settings_file = settings_dir / "settings.json"

            import os

            old_value = os.environ.get("JEAN_CLAUDE_STATE_DIR")
            os.environ["JEAN_CLAUDE_STATE_DIR"] = str(settings_dir)
            try:
                output = io.StringIO()
                with redirect_stdout(output):
                    code_set = main(["tools", "policy", "set", "allowlist"])
                    code_show = main(["tools", "policy", "show"])
                self.assertEqual(code_set, 0)
                self.assertEqual(code_show, 0)
                self.assertTrue(settings_file.exists())
                loaded = json.loads(settings_file.read_text(encoding="utf-8"))
                self.assertEqual(loaded["execution_policy"], "allowlist")
            finally:
                if old_value is None:
                    del os.environ["JEAN_CLAUDE_STATE_DIR"]
                else:
                    os.environ["JEAN_CLAUDE_STATE_DIR"] = old_value

    def test_cli_llm_debug_logs_to_stderr(self) -> None:
        output = io.StringIO()
        debug_output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(debug_output):
            exit_code = main(
                [
                    "llm",
                    "test",
                    "--provider",
                    "mock",
                    "--prompt",
                    "Find a thriller",
                    "--debug",
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertIn("[debug] llm.complete.request", debug_output.getvalue())
        self.assertIn("[debug] llm.complete.response", debug_output.getvalue())

    def test_cli_chat_debug_expands_newlines(self) -> None:
        output = io.StringIO()
        debug_output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(debug_output):
            exit_code = main(
                [
                    "chat",
                    "--provider",
                    "mock",
                    "--model",
                    "mock-v1",
                    "--message",
                    "hello",
                    "--debug",
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertIn("# Available Tools", debug_output.getvalue())
        self.assertIn("bash.run", debug_output.getvalue())


if __name__ == "__main__":
    unittest.main()
