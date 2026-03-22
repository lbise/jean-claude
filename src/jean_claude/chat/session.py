from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jean_claude.config import default_system_prompt_path
from jean_claude.errors import JeanClaudeError
from jean_claude.llm.base import DebugHook, LLMClient


@dataclass(slots=True)
class ChatMessage:
    role: str
    content: str


class ChatSession:
    def __init__(
        self,
        *,
        client: LLMClient,
        model: str,
        system_prompt_path: Path | None = None,
        history_turn_limit: int = 8,
        debug_hook: DebugHook | None = None,
    ) -> None:
        self.client = client
        self.model = model
        self.debug_hook = debug_hook
        self.history_turn_limit = max(1, history_turn_limit)
        self.system_prompt_path = (system_prompt_path or default_system_prompt_path()).expanduser().resolve()
        self.messages: list[ChatMessage] = []
        self._started = False

    def start(self) -> str:
        self._started = True
        return ""

    def ask(self, user_message: str) -> str:
        text = user_message.strip()
        if not text:
            raise ValueError("user_message must not be empty")

        if not self._started:
            self.start()

        result = self.client.complete(
            self._build_prompt(text),
            model=self.model,
            system_prompt=self._read_system_prompt(),
            debug_hook=self.debug_hook,
        )
        reply = result.text.strip()
        if not reply:
            reply = "I did not get a response back from the model."

        self.messages.append(ChatMessage(role="user", content=text))
        self.messages.append(ChatMessage(role="assistant", content=reply))
        return reply

    def _build_prompt(self, latest_user_message: str) -> str:
        history_lines = []
        for message in self._recent_messages():
            speaker = "User" if message.role == "user" else "Assistant"
            history_lines.append(f"{speaker}: {message.content}")

        history_text = "\n\n".join(history_lines) if history_lines else "(none yet)"
        return "\n\n".join(
            [
                "Continue the conversation and reply only with the assistant's next message.",
                "# Conversation History",
                history_text,
                "# Latest User Message",
                latest_user_message,
            ]
        )

    def _recent_messages(self) -> list[ChatMessage]:
        max_messages = self.history_turn_limit * 2
        if len(self.messages) <= max_messages:
            return list(self.messages)
        return self.messages[-max_messages:]

    def _read_system_prompt(self) -> str:
        try:
            text = self.system_prompt_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise JeanClaudeError(f"Unable to read system prompt file '{self.system_prompt_path}': {exc}") from exc

        if not text.strip():
            raise JeanClaudeError(f"System prompt file '{self.system_prompt_path}' is empty")
        return text
