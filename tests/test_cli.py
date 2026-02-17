from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

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


if __name__ == "__main__":
    unittest.main()
