from __future__ import annotations

import base64
import json
import unittest

from jean_claude.auth.openai_codex_oauth import (
    JWT_CLAIM_PATH,
    _parse_device_token_payload,
    _parse_device_user_code_payload,
    extract_account_id,
    parse_authorization_input,
)
from jean_claude.errors import AuthError


def _build_jwt(payload: dict[str, object]) -> str:
    header = {"alg": "none", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode("utf-8")).decode("ascii").rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
    return f"{header_b64}.{payload_b64}.x"


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


if __name__ == "__main__":
    unittest.main()
