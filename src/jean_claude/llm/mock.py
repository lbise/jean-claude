from __future__ import annotations

import json
from typing import Any

from jean_claude.llm.base import DebugHook, LLMResult


class MockLLMClient:
    provider_name = "mock"
    default_model = "mock-v1"

    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        debug_hook: DebugHook | None = None,
    ) -> LLMResult:
        selected_model = model or self.default_model
        mode = _detect_mode(system_prompt)

        _emit_debug(
            debug_hook,
            {
                "type": "llm.complete.request",
                "provider": self.provider_name,
                "model": selected_model,
                "system_prompt": system_prompt or "",
                "prompt": prompt,
                "mock_mode": mode,
            },
        )

        if mode == "tool_chat":
            payload = self._tool_chat_payload(prompt)
            result = LLMResult(
                provider=self.provider_name,
                model=selected_model,
                text=json.dumps(payload),
                usage={"input_tokens": 0, "output_tokens": 0},
                raw={"source": "mock", "mode": mode},
            )
        else:
            text = f"Mock response for: {prompt[:120]}"
            result = LLMResult(
                provider=self.provider_name,
                model=selected_model,
                text=text,
                usage={"input_tokens": 0, "output_tokens": 0},
                raw={"source": "mock", "mode": mode},
            )

        _emit_debug(
            debug_hook,
            {
                "type": "llm.complete.response",
                "provider": self.provider_name,
                "model": selected_model,
                "text": result.text,
                "usage": result.usage,
                "raw": result.raw,
            },
        )
        return result

    def _tool_chat_payload(self, prompt: str) -> dict[str, Any]:
        latest_message = _extract_block(prompt, "LATEST_USER_MESSAGE")
        text = latest_message.casefold()

        if "list" in text and ("home" in text or "directory" in text or "files" in text):
            return {
                "assistant_message": "Sure, I will list files in the home directory.",
                "tool_calls": [{"tool": "bash.run", "args": {"command": "ls -la ~"}}],
                "profile_patch": {},
                "done": False,
                "notes": ["mock selected bash tool"],
            }

        if "who am i" in text or "whoami" in text:
            return {
                "assistant_message": "Checking current user.",
                "tool_calls": [{"tool": "bash.run", "args": {"command": "whoami"}}],
                "profile_patch": {},
                "done": False,
                "notes": ["mock selected bash tool"],
            }

        return {
            "assistant_message": "Got it. I can run shell commands if you want me to.",
            "tool_calls": [],
            "profile_patch": {},
            "done": False,
            "notes": ["mock no tool needed"],
        }


def _detect_mode(system_prompt: str | None) -> str:
    prompt = system_prompt.casefold() if isinstance(system_prompt, str) else ""
    if "available tools" in prompt and "tool_calls" in prompt:
        return "tool_chat"
    return "generic"


def _extract_block(prompt: str, marker: str) -> str:
    start_tag = f"[{marker}]"
    end_tag = f"[/{marker}]"
    start = prompt.find(start_tag)
    if start == -1:
        return ""
    end = prompt.find(end_tag, start + len(start_tag))
    if end == -1:
        return ""
    return prompt[start + len(start_tag) : end].strip()


def _emit_debug(debug_hook: DebugHook | None, payload: dict[str, Any]) -> None:
    if debug_hook is not None:
        debug_hook(payload)
