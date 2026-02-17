from __future__ import annotations

import base64
import json
import unittest

from jean_claude.auth.openai_codex_oauth import JWT_CLAIM_PATH, extract_account_id, parse_authorization_input


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


if __name__ == "__main__":
    unittest.main()
