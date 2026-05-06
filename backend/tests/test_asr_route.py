"""Tests for the ``/v1/asr/transcribe`` route.

We mock the ``whisper_stt`` module wholesale because:
  - The real call hits Wiro's hosted Whisper, which costs money and
    is rate-limited per CI run.
  - The route is a thin wrapper over a single function — the
    interesting behaviour lives in the route's argument mapping,
    error translation, and size guard, not in transcription quality.

Coverage focus:
  - Happy path: ISO code → Wiro enum mapping, response shape.
  - Disabled path: 503 with the ``asr_disabled`` code mobile expects.
  - Empty + over-large bodies: 400 / 413 with the right code.
  - Upstream failure: 502 with ``asr_failed`` (whisper_stt returns
    ``None`` on auth/rate-limit/timeout).
  - Unknown ISO language: silent fallback to ``auto``.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class TestAsrTranscribeRoute(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("app.api.routes.asr.whisper_stt")
    def test_transcribe_disabled_returns_503(self, mock_stt) -> None:
        mock_stt.is_enabled.return_value = False
        files = {"audio": ("rec.m4a", b"fake-bytes", "audio/m4a")}
        resp = self.client.post(
            "/v1/asr/transcribe",
            files=files,
            data={"language": "tr"},
        )
        self.assertEqual(resp.status_code, 503)
        body = resp.json()
        self.assertEqual(body["detail"]["code"], "asr_disabled")
        self.assertIn("yazarak", body["detail"]["message_tr"])

    @patch("app.api.routes.asr.whisper_stt")
    def test_transcribe_success_maps_iso_to_wiro_enum(self, mock_stt) -> None:
        mock_stt.is_enabled.return_value = True
        mock_stt.transcribe.return_value = "Üç gündür baş ağrım var"
        files = {"audio": ("rec.m4a", b"audio-bytes", "audio/m4a")}
        resp = self.client.post(
            "/v1/asr/transcribe",
            files=files,
            data={"language": "tr"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["text"], "Üç gündür baş ağrım var")
        self.assertEqual(body["language"], "tr")
        self.assertEqual(body["provider"], "wiro_whisper")
        self.assertIn("model", body)
        self.assertIn("duration_ms", body)
        self.assertIsInstance(body["duration_ms"], int)
        # Verify the upstream call got the Wiro enum, not the ISO code.
        kwargs = mock_stt.transcribe.call_args.kwargs
        self.assertEqual(kwargs["language"], "Turkish")

    @patch("app.api.routes.asr.whisper_stt")
    def test_transcribe_empty_audio_returns_400(self, mock_stt) -> None:
        mock_stt.is_enabled.return_value = True
        files = {"audio": ("rec.m4a", b"", "audio/m4a")}
        resp = self.client.post(
            "/v1/asr/transcribe",
            files=files,
            data={"language": "tr"},
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertEqual(body["detail"]["code"], "empty_audio")
        # Ensure we didn't waste an upstream call on an empty body.
        mock_stt.transcribe.assert_not_called()

    @patch("app.api.routes.asr.whisper_stt")
    def test_transcribe_too_large_returns_413(self, mock_stt) -> None:
        mock_stt.is_enabled.return_value = True
        # 5 MB + 1 byte. Test relies on the route's _MAX_AUDIO_BYTES
        # constant — if you raise that, raise this too.
        oversized = b"X" * (5 * 1024 * 1024 + 1)
        files = {"audio": ("rec.m4a", oversized, "audio/m4a")}
        resp = self.client.post(
            "/v1/asr/transcribe",
            files=files,
            data={"language": "tr"},
        )
        self.assertEqual(resp.status_code, 413)
        body = resp.json()
        self.assertEqual(body["detail"]["code"], "audio_too_large")
        mock_stt.transcribe.assert_not_called()

    @patch("app.api.routes.asr.whisper_stt")
    def test_transcribe_upstream_failure_returns_502(self, mock_stt) -> None:
        # whisper_stt swallows Wiro auth/timeout/task errors and returns
        # None. The route must surface that as a 502, NOT a 200 with an
        # empty transcript — the mobile alert path depends on it.
        mock_stt.is_enabled.return_value = True
        mock_stt.transcribe.return_value = None
        files = {"audio": ("rec.m4a", b"some-bytes", "audio/m4a")}
        resp = self.client.post(
            "/v1/asr/transcribe",
            files=files,
            data={"language": "tr"},
        )
        self.assertEqual(resp.status_code, 502)
        body = resp.json()
        self.assertEqual(body["detail"]["code"], "asr_failed")

    @patch("app.api.routes.asr.whisper_stt")
    def test_transcribe_unknown_iso_falls_back_to_auto(self, mock_stt) -> None:
        # A bogus language code should NOT 422. Mobile setting a wrong
        # code shouldn't block the user from getting a transcript —
        # Whisper's autodetect handles our 5-language target fine.
        mock_stt.is_enabled.return_value = True
        mock_stt.transcribe.return_value = "yo"
        files = {"audio": ("rec.m4a", b"bytes", "audio/m4a")}
        resp = self.client.post(
            "/v1/asr/transcribe",
            files=files,
            data={"language": "xyz"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["language"], "auto")
        kwargs = mock_stt.transcribe.call_args.kwargs
        self.assertEqual(kwargs["language"], "auto")

    @patch("app.api.routes.asr.whisper_stt")
    def test_transcribe_default_language_is_tr(self, mock_stt) -> None:
        # If the client doesn't send a language form field, we default
        # to Turkish — the primary user base. "auto" would also be a
        # defensible default but Turkish is what mobile sends today.
        mock_stt.is_enabled.return_value = True
        mock_stt.transcribe.return_value = "merhaba"
        files = {"audio": ("rec.m4a", b"bytes", "audio/m4a")}
        resp = self.client.post(
            "/v1/asr/transcribe",
            files=files,
            # no `data={...}` — language omitted on purpose.
        )
        self.assertEqual(resp.status_code, 200)
        kwargs = mock_stt.transcribe.call_args.kwargs
        self.assertEqual(kwargs["language"], "Turkish")


if __name__ == "__main__":
    unittest.main()
