from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any

from jean_claude import __version__
from jean_claude.auth.store import OpenAICodexCredentials
from jean_claude.errors import AuthError


CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
REDIRECT_URI = "http://localhost:1455/auth/callback"
SCOPE = "openid profile email offline_access"
JWT_CLAIM_PATH = "https://api.openai.com/auth"

CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 1455
CALLBACK_PATH = "/auth/callback"
CALLBACK_TIMEOUT_SECONDS = 300
DEVICE_AUTH_TIMEOUT_SECONDS = 900
DEVICE_REDIRECT_URI = "https://auth.openai.com/deviceauth/callback"
DEVICE_AUTH_USERCODE_URL = "https://auth.openai.com/api/accounts/deviceauth/usercode"
DEVICE_AUTH_TOKEN_URL = "https://auth.openai.com/api/accounts/deviceauth/token"
DEVICE_AUTH_VERIFICATION_URL = "https://auth.openai.com/codex/device"
USER_AGENT = f"jean-claude/{__version__}"

SUCCESS_HTML = (
    "<!doctype html><html><head><meta charset='utf-8'><title>Authenticated</title>"
    "</head><body><p>Authentication successful. Return to your terminal.</p></body></html>"
)


@dataclass(slots=True)
class ParsedAuthorizationInput:
    code: str | None
    state: str | None


@dataclass(slots=True)
class DeviceAuthorizationSession:
    device_auth_id: str
    user_code: str
    interval_seconds: int


@dataclass(slots=True)
class DeviceAuthorizationGrant:
    authorization_code: str
    code_verifier: str


@dataclass(slots=True)
class _CallbackState:
    expected_state: str
    code: str | None = None
    error: str | None = None
    event: threading.Event = field(default_factory=threading.Event)


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    server: ThreadingHTTPServer

    def do_GET(self) -> None:  # noqa: N802
        state: _CallbackState = getattr(self.server, "callback_state")
        parsed = urlparse(self.path)
        if parsed.path != CALLBACK_PATH:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        params = parse_qs(parsed.query)
        callback_state = _first_param(params, "state")
        callback_code = _first_param(params, "code")

        if callback_state != state.expected_state:
            state.error = "State mismatch"
            state.event.set()
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"State mismatch")
            return

        if not callback_code:
            state.error = "Missing authorization code"
            state.event.set()
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing authorization code")
            return

        state.code = callback_code
        state.event.set()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(SUCCESS_HTML.encode("utf-8"))

    def log_message(self, _format: str, *_args: Any) -> None:
        return


class OAuthCallbackServer:
    def __init__(self, expected_state: str) -> None:
        self._state = _CallbackState(expected_state=expected_state)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        try:
            server = ThreadingHTTPServer((CALLBACK_HOST, CALLBACK_PORT), _OAuthCallbackHandler)
        except OSError:
            return False
        setattr(server, "callback_state", self._state)
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()
        return True

    def wait_for_code(self, timeout_seconds: int) -> str | None:
        if self._state.event.wait(timeout_seconds):
            if self._state.error:
                raise AuthError(self._state.error)
            return self._state.code
        return None

    def close(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge_bytes = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(challenge_bytes).decode("ascii").rstrip("=")
    return verifier, challenge


def parse_authorization_input(raw: str) -> ParsedAuthorizationInput:
    text = raw.strip()
    if not text:
        return ParsedAuthorizationInput(code=None, state=None)

    try:
        parsed_url = urlparse(text)
        if parsed_url.scheme and parsed_url.netloc:
            params = parse_qs(parsed_url.query)
            return ParsedAuthorizationInput(
                code=_first_param(params, "code"),
                state=_first_param(params, "state"),
            )
    except ValueError:
        pass

    if "#" in text:
        code, state = text.split("#", 1)
        return ParsedAuthorizationInput(code=code.strip() or None, state=state.strip() or None)

    if "code=" in text:
        params = parse_qs(text)
        return ParsedAuthorizationInput(
            code=_first_param(params, "code"),
            state=_first_param(params, "state"),
        )

    return ParsedAuthorizationInput(code=text, state=None)


def login_openai_codex(
    *,
    no_browser: bool = False,
    originator: str = "jean-claude",
    device_auth: bool = False,
) -> OpenAICodexCredentials:
    if device_auth:
        return login_openai_codex_device_code(originator=originator)

    verifier, challenge = generate_pkce_pair()
    expected_state = secrets.token_hex(16)

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": expected_state,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": originator,
    }
    auth_url = f"{AUTHORIZE_URL}?{urlencode(params)}"

    callback_server = OAuthCallbackServer(expected_state=expected_state)
    callback_started = callback_server.start()

    print("Open this URL to authenticate:")
    print(auth_url)

    if not no_browser:
        webbrowser.open(auth_url)

    try:
        code: str | None = None
        if callback_started:
            code = callback_server.wait_for_code(CALLBACK_TIMEOUT_SECONDS)

        if not code:
            pasted = input("Paste authorization code or full redirect URL: ").strip()
            parsed = parse_authorization_input(pasted)
            if parsed.state and parsed.state != expected_state:
                raise AuthError("State mismatch in pasted authorization data")
            code = parsed.code

        if not code:
            raise AuthError("No authorization code received")

        token_payload = exchange_authorization_code(code=code, verifier=verifier)
        account_id = extract_account_id(token_payload["access_token"])

        return OpenAICodexCredentials(
            access_token=token_payload["access_token"],
            refresh_token=token_payload["refresh_token"],
            expires_at_ms=int(time.time() * 1000 + token_payload["expires_in"] * 1000),
            account_id=account_id,
        )
    finally:
        callback_server.close()


def login_openai_codex_device_code(*, originator: str = "jean-claude") -> OpenAICodexCredentials:
    _ = originator
    session = _request_device_authorization_session()

    print("Follow these steps to sign in with ChatGPT device code:")
    print(f"1) Open: {DEVICE_AUTH_VERIFICATION_URL}")
    print(f"2) Enter code: {session.user_code}")
    print("This one-time code expires in about 15 minutes.")

    grant = _poll_device_authorization(session, timeout_seconds=DEVICE_AUTH_TIMEOUT_SECONDS)
    token_payload = exchange_authorization_code(
        code=grant.authorization_code,
        verifier=grant.code_verifier,
        redirect_uri=DEVICE_REDIRECT_URI,
    )
    account_id = extract_account_id(token_payload["access_token"])

    return OpenAICodexCredentials(
        access_token=token_payload["access_token"],
        refresh_token=token_payload["refresh_token"],
        expires_at_ms=int(time.time() * 1000 + token_payload["expires_in"] * 1000),
        account_id=account_id,
    )


def refresh_openai_codex_token(credentials: OpenAICodexCredentials) -> OpenAICodexCredentials:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": credentials.refresh_token,
        "client_id": CLIENT_ID,
    }
    token_payload = _token_request(data)
    account_id = extract_account_id(token_payload["access_token"])
    return OpenAICodexCredentials(
        access_token=token_payload["access_token"],
        refresh_token=token_payload["refresh_token"],
        expires_at_ms=int(time.time() * 1000 + token_payload["expires_in"] * 1000),
        account_id=account_id,
    )


def exchange_authorization_code(*, code: str, verifier: str, redirect_uri: str = REDIRECT_URI) -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": redirect_uri,
    }
    return _token_request(data)


def _request_device_authorization_session() -> DeviceAuthorizationSession:
    request = Request(
        DEVICE_AUTH_USERCODE_URL,
        data=json.dumps({"client_id": CLIENT_ID}).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )

    try:
        with urlopen(request, timeout=30.0) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404:
            raise AuthError(
                "Device code login is not enabled for this server. Retry without --device-auth."
            ) from exc
        raise AuthError(f"Device code request failed ({exc.code}): {body}") from exc
    except URLError as exc:
        raise AuthError(f"Device code request failed: {exc.reason}") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise AuthError("Device code response is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise AuthError("Device code response has invalid structure")

    return _parse_device_user_code_payload(payload)


def _poll_device_authorization(session: DeviceAuthorizationSession, *, timeout_seconds: int) -> DeviceAuthorizationGrant:
    started_at = time.monotonic()
    interval_seconds = max(session.interval_seconds, 1)

    while True:
        grant = _poll_device_authorization_once(session)
        if grant is not None:
            return grant

        elapsed = time.monotonic() - started_at
        if elapsed >= timeout_seconds:
            raise AuthError("Device code login timed out after 15 minutes")

        remaining_seconds = max(timeout_seconds - elapsed, 1.0)
        sleep_seconds = min(float(interval_seconds), remaining_seconds)
        time.sleep(sleep_seconds)


def _poll_device_authorization_once(session: DeviceAuthorizationSession) -> DeviceAuthorizationGrant | None:
    request = Request(
        DEVICE_AUTH_TOKEN_URL,
        data=json.dumps(
            {
                "device_auth_id": session.device_auth_id,
                "user_code": session.user_code,
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )

    try:
        with urlopen(request, timeout=30.0) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code in {403, 404}:
            return None
        raise AuthError(f"Device authorization failed ({exc.code}): {body}") from exc
    except URLError as exc:
        raise AuthError(f"Device authorization failed: {exc.reason}") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise AuthError("Device authorization response is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise AuthError("Device authorization response has invalid structure")

    return _parse_device_token_payload(payload)


def _parse_device_user_code_payload(payload: dict[str, Any]) -> DeviceAuthorizationSession:
    device_auth_id = payload.get("device_auth_id")
    if not isinstance(device_auth_id, str) or not device_auth_id.strip():
        raise AuthError("Device code response missing 'device_auth_id'")

    user_code = payload.get("user_code")
    if not isinstance(user_code, str) or not user_code.strip():
        user_code = payload.get("usercode")
    if not isinstance(user_code, str) or not user_code.strip():
        raise AuthError("Device code response missing 'user_code'")

    interval_raw = payload.get("interval", "5")
    try:
        interval_seconds = int(str(interval_raw).strip())
    except (TypeError, ValueError) as exc:
        raise AuthError("Device code response contains invalid 'interval'") from exc
    if interval_seconds < 1:
        interval_seconds = 1

    return DeviceAuthorizationSession(
        device_auth_id=device_auth_id.strip(),
        user_code=user_code.strip(),
        interval_seconds=interval_seconds,
    )


def _parse_device_token_payload(payload: dict[str, Any]) -> DeviceAuthorizationGrant:
    authorization_code = payload.get("authorization_code")
    if not isinstance(authorization_code, str) or not authorization_code.strip():
        raise AuthError("Device authorization response missing 'authorization_code'")

    code_verifier = payload.get("code_verifier")
    if not isinstance(code_verifier, str) or not code_verifier.strip():
        raise AuthError("Device authorization response missing 'code_verifier'")

    return DeviceAuthorizationGrant(
        authorization_code=authorization_code.strip(),
        code_verifier=code_verifier.strip(),
    )


def _token_request(data: dict[str, str]) -> dict[str, Any]:
    encoded = urlencode(data).encode("utf-8")
    request = Request(
        TOKEN_URL,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": USER_AGENT},
        method="POST",
    )

    try:
        with urlopen(request, timeout=30.0) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AuthError(f"OAuth token request failed ({exc.code}): {body}") from exc
    except URLError as exc:
        raise AuthError(f"OAuth token request failed: {exc.reason}") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise AuthError("OAuth token response is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise AuthError("OAuth token response has invalid structure")

    required = ("access_token", "refresh_token", "expires_in")
    for field_name in required:
        if field_name not in payload:
            raise AuthError(f"OAuth token response missing '{field_name}'")

    return payload


def extract_account_id(access_token: str) -> str:
    payload = _decode_jwt_payload(access_token)
    auth_data = payload.get(JWT_CLAIM_PATH)
    if not isinstance(auth_data, dict):
        raise AuthError("OAuth access token is missing OpenAI auth claim")
    account_id = auth_data.get("chatgpt_account_id")
    if not isinstance(account_id, str) or not account_id:
        raise AuthError("OAuth access token is missing chatgpt account id")
    return account_id


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("OAuth access token is not a JWT")
    payload_segment = parts[1]
    padding = "=" * ((4 - len(payload_segment) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload_segment + padding)
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise AuthError("Unable to decode OAuth JWT payload") from exc
    if not isinstance(payload, dict):
        raise AuthError("OAuth JWT payload is invalid")
    return payload


def _first_param(values: dict[str, list[str]], key: str) -> str | None:
    found = values.get(key)
    if not found:
        return None
    value = found[0].strip()
    return value or None
