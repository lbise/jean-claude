from __future__ import annotations

import base64
import json
import unittest
from unittest.mock import patch

from jean_claude.auth.openai_codex_oauth import (
    JWT_CLAIM_PATH,
    USER_AGENT,
    _parse_device_token_payload,
    _parse_device_user_code_payload,
    _request_device_authorization_session,
    _token_request,
    extract_account_id,
    parse_authorization_input,
)
from jean_claude.errors import AuthError


def _build_jwt(payload: dict[str, object]) -> str:
    header = {"alg": "none", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode("utf-8")).decode("ascii").rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
    return f"{header_b64}.{payload_b64}.x"


class _FakeResponse:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class OAuthHelpersTestCase(unittest.TestCase):
    def test_parse_authorization_input_from_url(self) -> None:
        parsed = parse_authorization_input("http://localhost:1455/auth/callback?code=abc123&state=xyz")
        self.assertEqual(parsed.code, "abc123")
        self.assertEqual(parsed.state, "xyz")

    def test_extract_account_id_from_access_token(self) -> None:
        token = _build_jwt({JWT_CLAIM_PATH: {"chatgpt_account_id": "acct_123"}})
        self.assertEqual(extract_account_id(token), "acct_123")

    def test_parse_device_user_code_payload_with_string_interval(self) -> None:
        session = _parse_device_user_code_payload(
            {
                "device_auth_id": "dev_123",
                "user_code": "ABCD-EFGH",
                "interval": "7",
            }
        )
        self.assertEqual(session.device_auth_id, "dev_123")
        self.assertEqual(session.user_code, "ABCD-EFGH")
        self.assertEqual(session.interval_seconds, 7)

    def test_parse_device_user_code_payload_supports_usercode_alias(self) -> None:
        session = _parse_device_user_code_payload(
            {
                "device_auth_id": "dev_456",
                "usercode": "IJKL-MNOP",
                "interval": 0,
            }
        )
        self.assertEqual(session.user_code, "IJKL-MNOP")
        self.assertEqual(session.interval_seconds, 1)

    def test_parse_device_user_code_payload_requires_fields(self) -> None:
        with self.assertRaises(AuthError):
            _parse_device_user_code_payload({"interval": "5"})

    @patch("jean_claude.auth.openai_codex_oauth.urlopen")
    def test_request_device_authorization_session_sets_user_agent(self, urlopen_mock) -> None:
        urlopen_mock.return_value = _FakeResponse(
            json.dumps(
                {
                    "device_auth_id": "dev_123",
                    "user_code": "ABCD-EFGH",
                    "interval": "5",
                }
            )
        )

        _request_device_authorization_session()

        request = urlopen_mock.call_args.args[0]
        self.assertEqual(request.headers.get("User-agent"), USER_AGENT)

    def test_parse_device_token_payload(self) -> None:
        grant = _parse_device_token_payload(
            {
                "authorization_code": "authcode_123",
                "code_verifier": "verifier_123",
            }
        )
        self.assertEqual(grant.authorization_code, "authcode_123")
        self.assertEqual(grant.code_verifier, "verifier_123")

    def test_parse_device_token_payload_requires_fields(self) -> None:
        with self.assertRaises(AuthError):
            _parse_device_token_payload({"authorization_code": "authcode_123"})

    @patch("jean_claude.auth.openai_codex_oauth.urlopen")
    def test_token_request_sets_user_agent(self, urlopen_mock) -> None:
        urlopen_mock.return_value = _FakeResponse(
            json.dumps(
                {
                    "access_token": "access_token",
                    "refresh_token": "refresh_token",
                    "expires_in": 3600,
                }
            )
        )

        _token_request({"grant_type": "refresh_token"})

        request = urlopen_mock.call_args.args[0]
        self.assertEqual(request.headers.get("User-agent"), USER_AGENT)


if __name__ == "__main__":
    unittest.main()
