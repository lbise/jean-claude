from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from jean_claude.chat import ChatSession
from jean_claude.auth.openai_codex_oauth import login_openai_codex
from jean_claude.auth.store import AuthStore
from jean_claude.errors import JeanClaudeError
from jean_claude.llm.base import DebugHook, LLMClient
from jean_claude.llm.openai_codex import DEFAULT_MODEL, OpenAICodexClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jc", description="Jean-Claude simple chat CLI")
    subparsers = parser.add_subparsers(dest="command")

    auth_parser = subparsers.add_parser("auth", help="Authentication commands")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command")

    auth_login = auth_subparsers.add_parser("login", help="Login with OAuth")
    auth_login.add_argument("provider", choices=["openai-codex"])
    auth_login.add_argument("--no-browser", action="store_true", help="Do not open a browser automatically")
    auth_login.add_argument("--device-auth", action="store_true", help="Use device code login for headless environments")

    auth_status = auth_subparsers.add_parser("status", help="Show auth status")
    auth_status.add_argument("provider", choices=["openai-codex"])

    auth_logout = auth_subparsers.add_parser("logout", help="Remove stored credentials")
    auth_logout.add_argument("provider", choices=["openai-codex"])

    chat_parser = subparsers.add_parser("chat", help="Open conversational chat mode")
    chat_parser.add_argument("--model", default=DEFAULT_MODEL)
    chat_parser.add_argument("--message", default=None, help="Send one message and exit")
    chat_parser.add_argument("--history-turns", type=int, default=8, help="Conversation turns kept in context")
    chat_parser.add_argument(
        "--system-prompt-file",
        default=None,
        help="Markdown file sent in full as the system prompt on every turn",
    )
    chat_parser.add_argument("--debug", action="store_true", help="Print LLM request/response debug logs")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "auth":
            return _run_auth(args)
        if args.command == "chat":
            return _run_chat(args)
        parser.print_help()
        return 0
    except JeanClaudeError as exc:
        print(f"Error: {exc}")
        return 1


def _run_auth(args: argparse.Namespace) -> int:
    store = AuthStore()

    if args.auth_command == "login":
        credentials = login_openai_codex(no_browser=args.no_browser, device_auth=args.device_auth)
        store.set_openai_codex(credentials)
        print("Stored credentials for openai-codex.")
        print(f"Account ID: {credentials.account_id}")
        print(f"Expires at: {_format_epoch_ms(credentials.expires_at_ms)}")
        return 0

    if args.auth_command == "status":
        credentials = store.get_openai_codex()
        if credentials is None:
            print("No credentials stored for openai-codex.")
            return 0
        now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
        status = "valid" if credentials.expires_at_ms > now_ms else "expired"
        print("Provider: openai-codex")
        print(f"Status: {status}")
        print(f"Account ID: {credentials.account_id}")
        print(f"Expires at: {_format_epoch_ms(credentials.expires_at_ms)}")
        return 0

    if args.auth_command == "logout":
        removed = store.delete_openai_codex()
        if removed:
            print("Removed credentials for openai-codex.")
        else:
            print("No credentials found for openai-codex.")
        return 0

    raise JeanClaudeError("Unknown auth command")


def _run_chat(args: argparse.Namespace) -> int:
    if args.history_turns < 1:
        raise JeanClaudeError("--history-turns must be >= 1")

    client = _build_llm_client(args.model)
    debug_hook = _build_debug_hook(args.debug)
    session = ChatSession(
        client=client,
        model=args.model,
        system_prompt_path=Path(args.system_prompt_file) if args.system_prompt_file else None,
        history_turn_limit=args.history_turns,
        debug_hook=debug_hook,
    )

    if args.message:
        response = session.ask(args.message)
        print(f"Jean-Claude: {response}")
        return 0

    print("Jean-Claude: Chat mode is on. Type /exit to quit, /system to show the active system prompt file, or @file.md to inline a Markdown file.")
    while True:
        try:
            user_message = input("You: ").strip()
        except EOFError:
            print()
            break

        if not user_message:
            continue

        command = user_message.casefold()
        if command in {"/exit", "/quit"}:
            print("Jean-Claude: Talk soon.")
            break
        if command in {"/help", "?"}:
            print("Jean-Claude: Commands: /exit, /system. Use @file.md to inline a Markdown file when it exists.")
            continue
        if command == "/system":
            print(f"Jean-Claude: Using system prompt file {session.system_prompt_path}")
            continue

        response = session.ask(user_message)
        print(f"Jean-Claude: {response}")

    return 0


def _build_llm_client(model: str) -> LLMClient:
    return OpenAICodexClient(store=AuthStore(), default_model=model)


def _format_epoch_ms(value: int) -> str:
    date = datetime.fromtimestamp(value / 1000, tz=UTC)
    return date.isoformat()


def _build_debug_hook(enabled: bool) -> DebugHook | None:
    if not enabled:
        return None

    def _hook(payload: dict[str, object]) -> None:
        event_type = str(payload.get("type", "debug"))
        sanitized, blocks = _extract_debug_blocks(payload)
        print(f"[debug] {event_type}", file=sys.stderr)
        print(json.dumps(sanitized, indent=2, sort_keys=True, default=str), file=sys.stderr)
        for path, text in blocks:
            print(f"[debug:block] {path}", file=sys.stderr)
            print(text, file=sys.stderr)

    return _hook


def _extract_debug_blocks(payload: dict[str, object]) -> tuple[dict[str, object], list[tuple[str, str]]]:
    blocks: list[tuple[str, str]] = []

    def _walk(value: object, path: str) -> object:
        if isinstance(value, dict):
            return {key: _walk(sub_value, f"{path}.{key}" if path else key) for key, sub_value in value.items()}

        if isinstance(value, list):
            return [_walk(item, f"{path}[{idx}]") for idx, item in enumerate(value)]

        if isinstance(value, str):
            stripped = value.strip()
            parsed = _try_parse_json_string(stripped)
            if parsed is not None and isinstance(parsed, (dict, list)):
                pretty = json.dumps(parsed, indent=2, sort_keys=True)
                blocks.append((path or "value", pretty))
                return f"<json string; see debug block '{path or 'value'}'>"

            if "\n" in value:
                blocks.append((path or "value", value))
                return f"<multiline string; see debug block '{path or 'value'}'>"

        return value

    sanitized_payload = _walk(payload, "")
    if not isinstance(sanitized_payload, dict):
        return payload, blocks
    return sanitized_payload, blocks


def _try_parse_json_string(value: str) -> object | None:
    if not value:
        return None
    if not (value.startswith("{") or value.startswith("[")):
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None
