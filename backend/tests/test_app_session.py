from __future__ import annotations

import time
import unittest

from app.services.app_session import (
    AppSessionUnauthorizedError,
    assert_app_session_from_cookie_header,
    build_main_app_entry_url,
    build_public_session_data,
    build_session_cookie_value,
    get_session_cookie_name,
    is_main_app_sso_required,
    read_app_session_from_cookie_header,
)


class AppSessionTests(unittest.TestCase):
    def env(self, **overrides: str) -> dict[str, str]:
        return {
            "REQUIRE_MAIN_APP_SSO": "true",
            "MAIN_APP_URL": "https://main.example.test",
            "MAIN_APP_DETAIL_IMAGE_AGENT_ENTRY_PATH": "/bot/detail-image-agent",
            "DETAIL_IMAGE_AGENT_SESSION_SECRET": "test-session-secret",
            **overrides,
        }

    def test_reads_valid_signed_cookie(self):
        env = self.env()
        cookie_value = build_session_cookie_value(
            token="main-token",
            user={"id": "user-1", "email": "user@example.test", "nickname": "User One"},
            main_app_url="https://main.example.test",
            expires_at_ms=int(time.time() * 1000) + 60_000,
            env=env,
        )

        session = read_app_session_from_cookie_header(
            f"{get_session_cookie_name(env)}={cookie_value}",
            env=env,
        )

        self.assertIsNotNone(session)
        self.assertEqual(session.token, "main-token")
        self.assertEqual(session.user["id"], "user-1")
        self.assertEqual(session.main_app_url, "https://main.example.test")

    def test_rejects_tampered_cookie_signature(self):
        env = self.env()
        cookie_value = build_session_cookie_value(
            token="main-token",
            user={"id": "user-1"},
            main_app_url="https://main.example.test",
            expires_at_ms=int(time.time() * 1000) + 60_000,
            env=env,
        )
        payload, _signature = cookie_value.split(".", 1)

        session = read_app_session_from_cookie_header(
            f"{get_session_cookie_name(env)}={payload}.bad-signature",
            env=env,
        )

        self.assertIsNone(session)

    def test_rejects_expired_cookie(self):
        env = self.env()
        cookie_value = build_session_cookie_value(
            token="main-token",
            user={"id": "user-1"},
            main_app_url="https://main.example.test",
            expires_at_ms=int(time.time() * 1000) - 1_000,
            env=env,
        )

        session = read_app_session_from_cookie_header(
            f"{get_session_cookie_name(env)}={cookie_value}",
            env=env,
        )

        self.assertIsNone(session)

    def test_assert_session_returns_local_user_when_sso_disabled(self):
        env = self.env(REQUIRE_MAIN_APP_SSO="false")

        session = assert_app_session_from_cookie_header("", "http://localhost:8000/api/session", env=env)

        self.assertEqual(session.user["id"], "detail-image-agent-local-dev-user")
        self.assertEqual(session.user["role"], "admin")

    def test_assert_session_raises_redirect_when_required_session_missing(self):
        env = self.env()

        with self.assertRaises(AppSessionUnauthorizedError) as context:
            assert_app_session_from_cookie_header("", "https://tool.example.test/api/session", env=env)

        self.assertEqual(context.exception.redirect_url, "https://main.example.test/bot/detail-image-agent")

    def test_public_session_data_hides_token(self):
        env = self.env()
        session = assert_app_session_from_cookie_header("", "http://localhost:8000/api/session", env={**env, "REQUIRE_MAIN_APP_SSO": "false"})

        public = build_public_session_data(session)

        self.assertIn("user", public)
        self.assertIn("expiresAt", public)
        self.assertNotIn("token", public)

    def test_main_app_entry_url_uses_configured_path(self):
        self.assertEqual(
            build_main_app_entry_url(env=self.env()),
            "https://main.example.test/bot/detail-image-agent",
        )

    def test_sso_required_defaults_to_production_only(self):
        self.assertFalse(is_main_app_sso_required({"NODE_ENV": "development"}))
        self.assertTrue(is_main_app_sso_required({"NODE_ENV": "production", "MAIN_APP_URL": "https://main.example.test"}))


if __name__ == "__main__":
    unittest.main()
