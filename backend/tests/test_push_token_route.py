"""Tests for POST /v1/triage/push-token and DELETE /v1/triage/push-token."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class PushTokenRouteTests(unittest.TestCase):
    def test_register_push_token_200_with_valid_body(self):
        with patch("app.push.register_token"):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/triage/push-token",
                    json={
                        "expo_push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
                        "device_id": "test-device-123",
                        "platform": "ios",
                        "locale": "tr-TR",
                    },
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_register_push_token_200_with_minimal_body(self):
        with patch("app.push.register_token"):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/triage/push-token",
                    json={
                        "expo_push_token": "ExponentPushToken[short]",
                        "device_id": "d1",
                    },
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_register_push_token_422_when_token_missing(self):
        with TestClient(app) as client:
            response = client.post(
                "/v1/triage/push-token",
                json={"device_id": "test-device-123"},
            )
        self.assertEqual(response.status_code, 422)

    def test_register_push_token_422_when_device_id_missing(self):
        with TestClient(app) as client:
            response = client.post(
                "/v1/triage/push-token",
                json={"expo_push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]"},
            )
        self.assertEqual(response.status_code, 422)

    def test_unregister_push_token_200_with_valid_body(self):
        with patch("app.push.unregister_token"):
            with TestClient(app) as client:
                response = client.request(
                    "DELETE",
                    "/v1/triage/push-token",
                    json={"device_id": "test-device-123"},
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_unregister_push_token_422_when_device_id_missing(self):
        with TestClient(app) as client:
            response = client.request(
                "DELETE",
                "/v1/triage/push-token",
                json={},
            )
        self.assertEqual(response.status_code, 422)

    def test_register_route_calls_push_service(self):
        with patch("app.push.register_token") as mocked_register:
            with TestClient(app) as client:
                response = client.post(
                    "/v1/triage/push-token",
                    json={
                        "expo_push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
                        "device_id": "test-device-123",
                        "platform": "android",
                        "locale": "en",
                    },
                )

        self.assertEqual(response.status_code, 200)
        mocked_register.assert_called_once_with(
            device_id="test-device-123",
            expo_token="ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
            platform="android",
            locale="en",
        )

    def test_unregister_route_calls_push_service(self):
        with patch("app.push.unregister_token") as mocked_unregister:
            with TestClient(app) as client:
                response = client.request(
                    "DELETE",
                    "/v1/triage/push-token",
                    json={"device_id": "test-device-123"},
                )

        self.assertEqual(response.status_code, 200)
        mocked_unregister.assert_called_once_with(device_id="test-device-123")

    def test_register_fail_open_in_development(self):
        with (
            patch("app.api.routes.push_token.settings.APP_ENV", "development"),
            patch("app.push.register_token", side_effect=RuntimeError("db down")),
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/triage/push-token",
                    json={
                        "expo_push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
                        "device_id": "test-device-123",
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_register_fail_closed_in_production(self):
        with (
            patch("app.api.routes.push_token.settings.APP_ENV", "production"),
            patch("app.push.register_token", side_effect=RuntimeError("db down")),
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/triage/push-token",
                    json={
                        "expo_push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
                        "device_id": "test-device-123",
                    },
                )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "PUSH_TOKEN_PERSIST_FAILED")

    def test_unregister_fail_closed_in_production(self):
        with (
            patch("app.api.routes.push_token.settings.APP_ENV", "production"),
            patch("app.push.unregister_token", side_effect=RuntimeError("db down")),
        ):
            with TestClient(app) as client:
                response = client.request(
                    "DELETE",
                    "/v1/triage/push-token",
                    json={"device_id": "test-device-123"},
                )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["action"], "unregister")


if __name__ == "__main__":
    unittest.main()
