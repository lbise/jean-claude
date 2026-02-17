from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

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

    def test_cli_prefs_show_json(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["prefs", "show", "--json"])
        self.assertEqual(exit_code, 0)
        self.assertIn('"genres_like"', output.getvalue())

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
                    "I loved Dune and Arrival",
                    "--no-profile",
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertIn("Jean-Claude:", output.getvalue())

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
                    "--no-profile",
                    "--debug",
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertIn("# Mode: Open Chat", debug_output.getvalue())
        self.assertIn("# Mode: Open Chat\n\nObjective:", debug_output.getvalue())


if __name__ == "__main__":
    unittest.main()
