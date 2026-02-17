from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jean_claude.conversation import ConversationEngine
from jean_claude.conversation.engine import OPEN_CHAT_MODE
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
        profile_context: dict[str, Any] | None = None,
        history_turn_limit: int = 8,
        debug_hook: DebugHook | None = None,
    ) -> None:
        self.engine = ConversationEngine(
            client=client,
            model=model,
            mode=OPEN_CHAT_MODE,
            initial_state={"profile": profile_context or {}},
            history_turn_limit=history_turn_limit,
            debug_hook=debug_hook,
        )
        self.messages: list[ChatMessage] = []
        self._started = False

    def start(self) -> str:
        if self._started:
            return ""
        self._started = True
        turn = self.engine.start()
        parts = [part for part in [turn.assistant_message, turn.next_question] if part]
        text = "\n".join(parts)
        if text:
            self.messages.append(ChatMessage(role="assistant", content=text))
        return text

    def ask(self, user_message: str) -> str:
        text = user_message.strip()
        if not text:
            raise ValueError("user_message must not be empty")

        if not self._started:
            self.start()

        self.messages.append(ChatMessage(role="user", content=text))
        turn = self.engine.reply(text)
        parts = [part for part in [turn.assistant_message, turn.next_question] if part]
        reply = "\n".join(parts).strip()
        if not reply:
            reply = "I heard you. Can you share a bit more detail?"
        self.messages.append(ChatMessage(role="assistant", content=reply))
        return reply
