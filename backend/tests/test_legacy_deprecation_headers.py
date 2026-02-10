from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes import session as session_routes
from app.api.routes.legacy_deprecation import (
    DEPRECATION_HEADER_VALUE,
    SUCCESSOR_LINK_HEADER_VALUE,
    SUNSET_HEADER_VALUE,
)
from app.main import app
from app.models.database import get_db


class _FakeDbSession:
    def add(self, _obj) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


async def _override_get_db():
    yield _FakeDbSession()


class LegacyDeprecationHeaderTests(unittest.TestCase):
    def test_session_start_returns_deprecation_headers(self):
        async def fake_handle_initial_symptoms(*_args, **_kwargs):
            return SimpleNamespace(
                action="emergency",
                message="acil",
                emergency=SimpleNamespace(
                    reason="Acil degerlendirme gerekli.",
                    emergency_instructions=["112'yi ara."],
                    missing_info_to_confirm=[],
                ),
            )

        app.dependency_overrides[get_db] = _override_get_db
        try:
            with patch.object(
                session_routes.orchestrator,
                "handle_initial_symptoms",
                fake_handle_initial_symptoms,
            ):
                with TestClient(app) as client:
                    response = client.post(
                        "/v1/session/start",
                        json={"user_input_tr": "basim donuyor"},
                    )
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Deprecation"], DEPRECATION_HEADER_VALUE)
        self.assertEqual(response.headers["Sunset"], SUNSET_HEADER_VALUE)
        self.assertEqual(response.headers["Link"], SUCCESSOR_LINK_HEADER_VALUE)


if __name__ == "__main__":
    unittest.main()
