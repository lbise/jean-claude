from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(slots=True)
class AgentSession:
    session_id: str
    flow_state: str
    user_profile: dict[str, Any] = field(default_factory=dict)
    history: list[ChatMessage] = field(default_factory=list)
