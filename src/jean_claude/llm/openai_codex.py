from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jean_claude.auth.openai_codex_oauth import refresh_openai_codex_token
from jean_claude.auth.store import AuthStore, OpenAICodexCredentials
from jean_claude.errors import AuthError, AuthExpiredError, LLMError, RetryableLLMError
from jean_claude.llm.base import DebugHook, LLMResult
from jean_claude.prompts import default_base_instructions


DEFAULT_MODEL = "gpt-5.3-codex"
DEFAULT_BASE_URL = "https://chatgpt.com/backend-api"
DEFAULT_TIMEOUT_SECONDS = 90.0
DEFAULT_INSTRUCTIONS = "You are Jean-Claude. Provide concise, practical answers."

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
USAGE_LIMIT_CODE_PATTERN = re.compile(r"usage_limit_reached|usage_not_included|rate_limit_exceeded", re.I)
RETRYABLE_TEXT_PATTERN = re.compile(
    r"rate.?limit|overloaded|service.?unavailable|upstream.?connect|connection.?refused",
    re.I,
)


class OpenAICodexClient:
    provider_name = "openai-codex"

    def __init__(
        self,
        *,
        store: AuthStore,
        default_model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = 3,
    ) -> None:
        self.store = store
        self.default_model = default_model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        debug_hook: DebugHook | None = None,
    ) -> LLMResult:
        if not prompt.strip():
            raise LLMError("Prompt must not be empty")

        selected_model = model or self.default_model
        effective_system_prompt = self._resolve_system_prompt(system_prompt)
        _emit_debug(
            debug_hook,
            {
                "type": "llm.complete.request",
                "provider": self.provider_name,
                "model": selected_model,
                "system_prompt": effective_system_prompt,
                "prompt": prompt,
            },
        )
        credentials = self._require_credentials()
        credentials = self._ensure_fresh_credentials(credentials)

        refreshed_after_401 = False
        for attempt in range(self.max_retries + 1):
            try:
                result = self._request_once(
                    credentials=credentials,
                    model=selected_model,
                    prompt=prompt,
                    system_prompt=effective_system_prompt,
                    debug_hook=debug_hook,
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
            except AuthExpiredError:
                if refreshed_after_401:
                    raise
                credentials = self._refresh_and_store(credentials)
                refreshed_after_401 = True
            except RetryableLLMError as exc:
                if attempt >= self.max_retries:
                    raise LLMError(str(exc)) from exc
                delay = 2**attempt
                time.sleep(delay)

        raise LLMError("OpenAI Codex request failed")

    def _require_credentials(self) -> OpenAICodexCredentials:
        credentials = self.store.get_openai_codex()
        if credentials is None:
            raise AuthError("No openai-codex credentials found. Run 'jc auth login openai-codex'.")
        return credentials

    def _ensure_fresh_credentials(self, credentials: OpenAICodexCredentials) -> OpenAICodexCredentials:
        now_ms = int(time.time() * 1000)
        refresh_margin_ms = 30_000
        if credentials.expires_at_ms > now_ms + refresh_margin_ms:
            return credentials
        return self._refresh_and_store(credentials)

    def _refresh_and_store(self, credentials: OpenAICodexCredentials) -> OpenAICodexCredentials:
        refreshed = refresh_openai_codex_token(credentials)
        self.store.set_openai_codex(refreshed)
        return refreshed

    def _request_once(
        self,
        *,
        credentials: OpenAICodexCredentials,
        model: str,
        prompt: str,
        system_prompt: str,
        debug_hook: DebugHook | None,
    ) -> LLMResult:
        url = f"{self.base_url}/codex/responses"
        headers = {
            "Authorization": f"Bearer {credentials.access_token}",
            "chatgpt-account-id": credentials.account_id,
            "OpenAI-Beta": "responses=experimental",
            "originator": "jean-claude",
            "accept": "text/event-stream",
            "content-type": "application/json",
            "user-agent": "jean-claude/0.1.0",
        }
        body = self._build_request_body(model=model, prompt=prompt, system_prompt=system_prompt)
        _emit_debug(
            debug_hook,
            {
                "type": "llm.http.request",
                "provider": self.provider_name,
                "url": url,
                "headers": _redact_headers(headers),
                "json_body": body,
            },
        )

        text_chunks: list[str] = []
        completed_response: dict[str, Any] | None = None
        response_status_code: int | None = None

        request = Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_status_code = int(response.getcode() or 200)
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue

                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue

                    event = self._parse_sse_event(payload)
                    if event is None:
                        continue

                    event_type = str(event.get("type", ""))
                    if event_type == "error":
                        message = self._extract_event_error_message(event)
                        raise LLMError(message)
                    if event_type == "response.failed":
                        message = self._extract_response_failed_message(event)
                        raise LLMError(message)

                    delta = event.get("delta")
                    if isinstance(delta, str):
                        text_chunks.append(delta)

                    if event_type in {"response.completed", "response.done"}:
                        response_data = event.get("response")
                        if isinstance(response_data, dict):
                            completed_response = response_data
        except HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            _emit_debug(
                debug_hook,
                {
                    "type": "llm.http.error",
                    "provider": self.provider_name,
                    "status_code": exc.code,
                    "body": body_text,
                },
            )
            self._raise_for_http_error(exc.code, body_text)
        except URLError as exc:
            message = str(exc.reason) if getattr(exc, "reason", None) else str(exc)
            raise RetryableLLMError(f"Network error while calling OpenAI Codex: {message}") from exc
        except TimeoutError as exc:
            raise RetryableLLMError("Timed out while calling OpenAI Codex") from exc

        text = "".join(text_chunks).strip()
        if not text:
            text = self._extract_text_from_completed_response(completed_response)
        if not text:
            raise LLMError("OpenAI Codex returned no text output")

        usage = completed_response.get("usage", {}) if isinstance(completed_response, dict) else {}
        usage_data = usage if isinstance(usage, dict) else {}
        _emit_debug(
            debug_hook,
            {
                "type": "llm.http.response",
                "provider": self.provider_name,
                "status_code": response_status_code or 200,
                "output_text": text,
                "usage": usage_data,
                "response": completed_response,
            },
        )

        return LLMResult(
            provider=self.provider_name,
            model=model,
            text=text,
            usage=usage_data,
            raw={"response": completed_response} if completed_response else None,
        )

    def _build_request_body(self, *, model: str, prompt: str, system_prompt: str | None) -> dict[str, Any]:
        content = [{"type": "input_text", "text": prompt}]
        instructions = system_prompt.strip() if isinstance(system_prompt, str) and system_prompt.strip() else DEFAULT_INSTRUCTIONS
        body: dict[str, Any] = {
            "model": model,
            "store": False,
            "stream": True,
            "instructions": instructions,
            "input": [{"role": "user", "content": content}],
            "text": {"verbosity": "medium"},
            "include": ["reasoning.encrypted_content"],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
        }
        return body

    def _parse_sse_event(self, payload: str) -> dict[str, Any] | None:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        return data

    def _extract_event_error_message(self, event: dict[str, Any]) -> str:
        error = event.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
        message = event.get("message")
        if isinstance(message, str) and message:
            return message
        return "OpenAI Codex reported an error"

    def _extract_response_failed_message(self, event: dict[str, Any]) -> str:
        response = event.get("response")
        if isinstance(response, dict):
            error = response.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if isinstance(message, str) and message:
                    return message
        return "OpenAI Codex response failed"

    def _extract_text_from_completed_response(self, response: dict[str, Any] | None) -> str:
        if not isinstance(response, dict):
            return ""

        output_text = response.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        output = response.get("output")
        if not isinstance(output, list):
            return ""

        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue

            if item.get("type") != "message":
                continue

            content = item.get("content")
            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type not in {"output_text", "text"}:
                    continue
                block_text = block.get("text")
                if isinstance(block_text, str) and block_text:
                    parts.append(block_text)

        return "".join(parts).strip()

    def _raise_for_http_error(self, status_code: int, body_text: str) -> None:
        code = ""
        message = body_text.strip() or f"HTTP {status_code}"

        try:
            payload = json.loads(body_text)
            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    parsed_message = error.get("message")
                    parsed_code = error.get("code") or error.get("type")
                    if isinstance(parsed_message, str) and parsed_message:
                        message = parsed_message
                    if isinstance(parsed_code, str):
                        code = parsed_code
        except json.JSONDecodeError:
            pass

        if status_code == 401:
            raise AuthExpiredError("OpenAI Codex authentication expired or invalid")

        if code and USAGE_LIMIT_CODE_PATTERN.search(code):
            raise LLMError("ChatGPT usage limit reached for the current plan")

        if status_code in RETRYABLE_STATUS_CODES or RETRYABLE_TEXT_PATTERN.search(message):
            raise RetryableLLMError(f"Transient Codex error ({status_code}): {message}")

        raise LLMError(f"OpenAI Codex request failed ({status_code}): {message}")

    def _resolve_system_prompt(self, system_prompt: str | None) -> str:
        if isinstance(system_prompt, str) and system_prompt.strip():
            return system_prompt.strip()
        try:
            return default_base_instructions()
        except Exception:
            return DEFAULT_INSTRUCTIONS


def _emit_debug(debug_hook: DebugHook | None, payload: dict[str, Any]) -> None:
    if debug_hook is not None:
        debug_hook(payload)


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        if key.casefold() == "authorization":
            redacted[key] = "Bearer <redacted>"
        else:
            redacted[key] = value
    return redacted
