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
from jean_claude.llm.mock import MockLLMClient
from jean_claude.llm.openai_codex import DEFAULT_MODEL, OpenAICodexClient
from jean_claude.prefs import PreferencesStore, run_interview, summarize_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jc", description="Jean-Claude LLM chat CLI")
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

    llm_parser = subparsers.add_parser("llm", help="LLM commands")
    llm_subparsers = llm_parser.add_subparsers(dest="llm_command")

    llm_test = llm_subparsers.add_parser("test", help="Run a simple LLM test prompt")
    llm_test.add_argument("--provider", choices=["openai-codex", "mock"], default="openai-codex")
    llm_test.add_argument("--model", default=DEFAULT_MODEL)
    llm_test.add_argument("--prompt", required=True)
    llm_test.add_argument("--system", default=None, help="Optional system prompt")
    llm_test.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    llm_test.add_argument("--debug", action="store_true", help="Print LLM request/response debug logs")

    chat_parser = subparsers.add_parser("chat", help="Open conversational chat mode")
    chat_parser.add_argument("--provider", choices=["openai-codex", "mock"], default="openai-codex")
    chat_parser.add_argument("--model", default=DEFAULT_MODEL)
    chat_parser.add_argument("--message", default=None, help="Send one message and exit")
    chat_parser.add_argument("--history-turns", type=int, default=8, help="Conversation turns kept in context")
    chat_parser.add_argument(
        "--system-prompt-file",
        default=None,
        help="Markdown file sent in full as the system prompt on every turn",
    )
    chat_parser.add_argument("--debug", action="store_true", help="Print LLM request/response debug logs")

    prefs_parser = subparsers.add_parser("prefs", help="User preference profile commands")
    prefs_subparsers = prefs_parser.add_subparsers(dest="prefs_command")

    prefs_interview = prefs_subparsers.add_parser("interview", help="Run interactive preference interview")
    prefs_interview.add_argument("--provider", choices=["openai-codex", "mock"], default="openai-codex")
    prefs_interview.add_argument("--model", default=DEFAULT_MODEL)
    prefs_interview.add_argument("--max-turns", type=int, default=8)
    prefs_interview.add_argument("--json", action="store_true", help="Print resulting profile as JSON")
    prefs_interview.add_argument("--debug", action="store_true", help="Print LLM request/response debug logs")

    prefs_show = prefs_subparsers.add_parser("show", help="Show saved preference profile")
    prefs_show.add_argument("--json", action="store_true", help="Print machine-readable JSON output")

    prefs_reset = prefs_subparsers.add_parser("reset", help="Reset saved preference profile")
    prefs_reset.add_argument("--yes", action="store_true", help="Skip confirmation prompt")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "auth":
            return _run_auth(args)
        if args.command == "llm":
            return _run_llm(args)
        if args.command == "chat":
            return _run_chat(args)
        if args.command == "prefs":
            return _run_prefs(args)
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


def _run_llm(args: argparse.Namespace) -> int:
    if args.llm_command != "test":
        raise JeanClaudeError("Unknown llm command")

    client = _build_llm_client(args.provider, args.model)
    debug_hook = _build_debug_hook(args.debug)

    result = client.complete(
        args.prompt,
        model=args.model,
        system_prompt=args.system,
        debug_hook=debug_hook,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "provider": result.provider,
                    "model": result.model,
                    "text": result.text,
                    "usage": result.usage,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    print(f"Provider: {result.provider}")
    print(f"Model: {result.model}")
    if result.usage:
        print(f"Usage: {json.dumps(result.usage, sort_keys=True)}")
    print("Text:")
    print(result.text)
    return 0


def _run_prefs(args: argparse.Namespace) -> int:
    store = PreferencesStore()

    if args.prefs_command == "show":
        profile = store.load()
        if args.json:
            print(json.dumps(profile, indent=2, sort_keys=True))
            return 0

        print("Saved preferences:")
        for line in summarize_profile(profile):
            print(f"- {line}")
        return 0

    if args.prefs_command == "reset":
        if not args.yes:
            confirmation = input("This will overwrite your saved profile. Continue? [y/N]: ").strip().casefold()
            if confirmation not in {"y", "yes"}:
                print("Cancelled.")
                return 0
        store.save({})
        print("Reset preference profile.")
        return 0

    if args.prefs_command == "interview":
        if args.max_turns < 1:
            raise JeanClaudeError("--max-turns must be >= 1")
        client = _build_llm_client(args.provider, args.model)
        debug_hook = _build_debug_hook(args.debug)
        profile = run_interview(
            client=client,
            model=args.model,
            store=store,
            max_turns=args.max_turns,
            debug_hook=debug_hook,
        )
        if args.json:
            print(json.dumps(profile, indent=2, sort_keys=True))
        return 0

    raise JeanClaudeError("Unknown prefs command")


def _run_chat(args: argparse.Namespace) -> int:
    if args.history_turns < 1:
        raise JeanClaudeError("--history-turns must be >= 1")

    client = _build_llm_client(args.provider, args.model)
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

    print("Jean-Claude: Chat mode is on. Type /exit to quit, /system to show the active system prompt file.")
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
            print("Jean-Claude: Commands: /exit, /system")
            continue
        if command == "/system":
            print(f"Jean-Claude: Using system prompt file {session.system_prompt_path}")
            continue

        response = session.ask(user_message)
        print(f"Jean-Claude: {response}")

    return 0


def _build_llm_client(provider: str, model: str) -> LLMClient:
    if provider == "openai-codex":
        return OpenAICodexClient(store=AuthStore(), default_model=model)
    return MockLLMClient()


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
