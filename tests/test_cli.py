from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from jean_claude.auth.store import OpenAICodexCredentials
from jean_claude.cli import build_parser, main
from jean_claude.llm.base import LLMResult


class RecordingLLMClient:
    def __init__(self, response: str = "Stub reply") -> None:
        self.response = response
        self.calls: list[dict[str, str]] = []

    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        debug_hook=None,
    ) -> LLMResult:
        self.calls.append(
            {
                "model": model or "",
                "prompt": prompt,
                "system_prompt": system_prompt or "",
            }
        )
        if debug_hook is not None:
            debug_hook(
                {
                    "type": "llm.complete.request",
                    "provider": "recording",
                    "model": model or "recording-v1",
                    "prompt": prompt,
                    "system_prompt": system_prompt or "",
                }
            )
        result = LLMResult(provider="recording", model=model or "recording-v1", text=self.response)
        if debug_hook is not None:
            debug_hook(
                {
                    "type": "llm.complete.response",
                    "provider": result.provider,
                    "model": result.model,
                    "text": result.text,
                    "usage": result.usage,
                    "raw": result.raw,
                }
            )
        return result


class CLITestCase(unittest.TestCase):
    def test_cli_auth_parser_accepts_device_auth_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["auth", "login", "openai-codex", "--device-auth"])
        self.assertTrue(args.device_auth)

    def test_cli_auth_login_passes_device_auth_flag(self) -> None:
        credentials = OpenAICodexCredentials(
            access_token="access",
            refresh_token="refresh",
            expires_at_ms=1_700_000_000_000,
            account_id="acct_123",
        )
        output = io.StringIO()

        with patch("jean_claude.cli.login_openai_codex", return_value=credentials) as login_mock, patch(
            "jean_claude.cli.AuthStore"
        ) as store_cls:
            with redirect_stdout(output):
                exit_code = main(["auth", "login", "openai-codex", "--device-auth", "--no-browser"])

        self.assertEqual(exit_code, 0)
        login_mock.assert_called_once_with(no_browser=True, device_auth=True)
        store_cls.return_value.set_openai_codex.assert_called_once_with(credentials)

    def test_cli_chat_parser_accepts_system_prompt_file(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["chat", "--system-prompt-file", "prompts/system.md"])
        self.assertEqual(args.system_prompt_file, "prompts/system.md")

    def test_cli_chat_one_shot(self) -> None:
        output = io.StringIO()
        client = RecordingLLMClient(response="Here is a reply")
        with TemporaryDirectory() as temp_dir:
            system_prompt_path = Path(temp_dir) / "system.md"
            system_prompt_path.write_text("# Prompt\n\nBe helpful.", encoding="utf-8")
            with patch("jean_claude.cli._build_llm_client", return_value=client):
                with redirect_stdout(output):
                    exit_code = main(
                        [
                            "chat",
                            "--model",
                            "gpt-5.3-codex",
                            "--message",
                            "I loved Dune and Arrival",
                            "--system-prompt-file",
                            str(system_prompt_path),
                        ]
                    )
        self.assertEqual(exit_code, 0)
        self.assertIn("Jean-Claude: Here is a reply", output.getvalue())
        self.assertIn("# Latest User Message\n\nI loved Dune and Arrival", client.calls[0]["prompt"])

    def test_cli_chat_debug_expands_newlines(self) -> None:
        output = io.StringIO()
        debug_output = io.StringIO()
        client = RecordingLLMClient(response="hello")
        with TemporaryDirectory() as temp_dir:
            system_prompt_path = Path(temp_dir) / "system.md"
            system_prompt_path.write_text("# Prompt\n\nBe helpful.", encoding="utf-8")
            with patch("jean_claude.cli._build_llm_client", return_value=client):
                with redirect_stdout(output), redirect_stderr(debug_output):
                    exit_code = main(
                        [
                            "chat",
                            "--model",
                            "gpt-5.3-codex",
                            "--message",
                            "hello",
                            "--system-prompt-file",
                            str(system_prompt_path),
                            "--debug",
                        ]
                    )
        self.assertEqual(exit_code, 0)
        self.assertIn("[debug] llm.complete.request", debug_output.getvalue())
        self.assertIn("[debug] llm.complete.response", debug_output.getvalue())
        self.assertIn("# Prompt", debug_output.getvalue())
        self.assertIn("# Latest User Message", debug_output.getvalue())

    def test_cli_chat_one_shot_expands_markdown_references_in_debug_prompt(self) -> None:
        output = io.StringIO()
        debug_output = io.StringIO()
        client = RecordingLLMClient(response="done")
        with TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            system_prompt_path = base_path / "system.md"
            notes_path = base_path / "notes.md"
            system_prompt_path.write_text("# Prompt\n\nBe helpful.", encoding="utf-8")
            notes_path.write_text("# Notes\n\nShip the release.", encoding="utf-8")
            with patch("jean_claude.chat.session.Path.cwd", return_value=base_path):
                with patch("jean_claude.cli._build_llm_client", return_value=client):
                    with redirect_stdout(output), redirect_stderr(debug_output):
                        exit_code = main(
                            [
                                "chat",
                                "--model",
                                "gpt-5.3-codex",
                                "--message",
                                "Summarize @notes.md",
                                "--system-prompt-file",
                                str(system_prompt_path),
                                "--debug",
                            ]
                        )
        self.assertEqual(exit_code, 0)
        self.assertIn("[Included markdown file: notes.md]", debug_output.getvalue())
        self.assertIn("# Notes\n\nShip the release.", debug_output.getvalue())


if __name__ == "__main__":
    unittest.main()
