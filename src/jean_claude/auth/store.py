from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jean_claude.config import auth_file_path
from jean_claude.errors import AuthError


OPENAI_CODEX_PROVIDER = "openai-codex"


@dataclass(slots=True)
class OpenAICodexCredentials:
    access_token: str
    refresh_token: str
    expires_at_ms: int
    account_id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OpenAICodexCredentials":
        return cls(
            access_token=str(data["access_token"]),
            refresh_token=str(data["refresh_token"]),
            expires_at_ms=int(data["expires_at_ms"]),
            account_id=str(data["account_id"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at_ms": self.expires_at_ms,
            "account_id": self.account_id,
        }


class AuthStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or auth_file_path()

    def get_openai_codex(self) -> OpenAICodexCredentials | None:
        raw = self._load_raw()
        providers = raw.get("providers", {})
        data = providers.get(OPENAI_CODEX_PROVIDER)
        if not isinstance(data, dict):
            return None
        try:
            return OpenAICodexCredentials.from_dict(data)
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthError("Stored openai-codex credentials are invalid") from exc

    def set_openai_codex(self, credentials: OpenAICodexCredentials) -> None:
        raw = self._load_raw()
        providers = raw.setdefault("providers", {})
        providers[OPENAI_CODEX_PROVIDER] = credentials.to_dict()
        self._save_raw(raw)

    def delete_openai_codex(self) -> bool:
        raw = self._load_raw()
        providers = raw.get("providers", {})
        if OPENAI_CODEX_PROVIDER not in providers:
            return False
        del providers[OPENAI_CODEX_PROVIDER]
        self._save_raw(raw)
        return True

    def _load_raw(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"providers": {}}
        try:
            content = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise AuthError(f"Unable to read auth store: {self.path}") from exc
        if not content.strip():
            return {"providers": {}}
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AuthError(f"Auth store is not valid JSON: {self.path}") from exc
        if not isinstance(data, dict):
            raise AuthError("Auth store root must be a JSON object")
        return data

    def _save_raw(self, raw: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass

        payload = json.dumps(raw, indent=2, sort_keys=True) + "\n"
        fd, temp_name = tempfile.mkstemp(prefix=".auth-", dir=str(self.path.parent), text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file_handle:
                file_handle.write(payload)
            try:
                os.chmod(temp_name, 0o600)
            except OSError:
                pass
            os.replace(temp_name, self.path)
        except OSError as exc:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise AuthError(f"Unable to write auth store: {self.path}") from exc
