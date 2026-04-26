from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    # LLM
    WIRO_API_KEY: str = ""
    WIRO_API_SECRET: str = ""
    WIRO_BASE_URL: str = "https://api.wiro.ai"
    LLM_MODEL: str = "gpt-5-2"
    WIRO_REASONING: str = "medium"
    WIRO_WEB_SEARCH: bool = False
    WIRO_VERBOSITY: str = "medium"
    WIRO_POLL_INTERVAL_SECONDS: float = 1.0
    WIRO_POLL_TIMEOUT_SECONDS: float = 90.0
    WIRO_HTTP_TIMEOUT_SECONDS: float = 60.0

    # Database (SQLite default for easy dev; set to postgresql+asyncpg://... for production)
    DATABASE_URL: str = "sqlite+aiosqlite:///./dotshub.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_DB_URL: str = ""
    IP_HASH_SALT: str = "salt"

    # Facility discovery (Nominatim)
    FACILITY_DISCOVERY_ENABLED: bool = True
    FACILITY_DISCOVERY_TIMEOUT_SECONDS: float = 2.5

    # App
    APP_ENV: str = "development"
    DEBUG: bool = True
    # Allowed CORS origins. Two accepted formats:
    #   JSON array:  ["http://localhost:3000","https://x.com"]
    #   CSV:         http://localhost:3000,https://x.com
    # The JSON shape is stricter (required-quoted strings) but
    # round-trips safely through pydantic/typed env readers; the CSV
    # shape is human-friendlier and — crucially — avoids PowerShell
    # quote-escape footguns when setting secrets via `flyctl secrets
    # set`. A bad value here crashes the app on import (FastAPI never
    # reaches a request), so tolerance-at-read is worth the 3 lines.
    CORS_ORIGINS: str = '["http://localhost:8081","http://localhost:19006","http://localhost:3000"]'
    ADMIN_API_KEY: str = ""

    # Webhook notifications
    WEBHOOK_ENABLED: bool = False
    WEBHOOK_SLACK_URL: str = ""
    WEBHOOK_DISCORD_URL: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        """Return the CORS allow-list.

        Accepts either a JSON array (`["a","b"]`) or a comma-separated
        value (`a,b`). Leading/trailing whitespace on the whole value
        and each CSV entry is stripped. An empty / whitespace-only
        `CORS_ORIGINS` returns `[]` (FastAPI's CORSMiddleware will then
        allow no cross-origin request — deliberate fail-closed for
        production where forgetting this env was previously a silent
        "all origins" footgun).

        A bad JSON array surfaces a clear error instead of the raw
        `json.decoder.JSONDecodeError` we used to ship to users
        (imprint at Faz A2 Fly deploy — commit 90c7411 followup).
        """
        raw = (self.CORS_ORIGINS or "").strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                # Re-raise with context so ops sees what was actually
                # read from env instead of a generic JSON traceback.
                raise ValueError(
                    f"CORS_ORIGINS starts with '[' but is not valid JSON. "
                    f"Got: {raw!r}. Original error: {exc.msg}"
                ) from exc
            if not isinstance(parsed, list):  # pragma: no cover - defensive: JSON starting with '[' always parses to a list
                raise ValueError(
                    f"CORS_ORIGINS JSON must be a list; got {type(parsed).__name__}: {parsed!r}"
                )
            return [str(v).strip() for v in parsed if str(v).strip()]
        # CSV fallback — trim whitespace, drop empty slots.
        return [v.strip() for v in raw.split(",") if v.strip()]

    # Agent config
    MAX_QUESTIONS: int = 6
    TEMPERATURE: float = 0.3

    # ── LLM NLU — Wiro.ai provider (gemini-2-5-flash) ─────────────────────────
    # Provider choices: "wiro" | "google" | "anthropic" | "openai"
    # "wiro" uses WIRO_API_KEY and the Wiro submit+poll API (recommended).
    # Other providers call the respective vendor API directly.
    LLM_PROVIDER: str = "wiro"
    # LLM_API_KEY: only needed for non-Wiro providers.
    # For "wiro", WIRO_API_KEY is reused automatically.
    LLM_API_KEY: str = ""
    # Wiro model path  →  https://api.wiro.ai/v1/Run/{LLM_NLU_MODEL}
    LLM_NLU_MODEL: str = "google/gemini-2-5-flash"
    LLM_NLU_ENABLED: bool = False            # feature flag — off by default
    # Hard deadline for the entire submit+poll cycle (seconds)
    LLM_NLU_TIMEOUT_SECONDS: float = 15.0
    # How often to poll Wiro for task completion
    LLM_NLU_POLL_INTERVAL_SECONDS: float = 0.5
    LLM_NLU_LOG_TO_SUPABASE: bool = True
    LLM_EXPLAIN_ENABLED: bool = False        # optional explanation layer (B9)

    # ── Health-tourism: LLM fallback for procedure-intent extraction ─────
    # When the deterministic synonym matcher (services/procedure_intent.py)
    # returns confidence below the threshold, fall back to an LLM call
    # that picks one of the known procedure ids. Off by default —
    # operators flip this on when they observe a meaningful tail of
    # PROCEDURE_UNRESOLVED or low-confidence quotes in the analytics.
    LLM_PROCEDURE_INTENT_ENABLED: bool = False
    LLM_PROCEDURE_INTENT_MIN_CONFIDENCE: float = 0.40

    # When the primary procedure-intent LLM (Gemini Flash via the legacy
    # llm_nlu_client) returns no usable answer (network failure, schema
    # error, ``id="none"``, or hallucinated id), retry the same prompt
    # against Wiro/Qwen3.6-27B as a last-tier fallback. Off by default —
    # operators flip this on when they observe Gemini Flash returning
    # ``id="none"`` for clear Turkish input that Qwen handles better.
    # Both ``WIRO_QWEN_LLM_ENABLED`` and ``WIRO_API_SECRET`` must also
    # be set for this fallback to actually run.
    LLM_PROCEDURE_INTENT_QWEN_FALLBACK_ENABLED: bool = False

    # ── Wiro AI services (health-tourism extensions) ────────────────────
    # Each service is a thin wrapper around the existing Wiro
    # submit+poll pattern (HMAC auth from llm_nlu_client). Feature
    # flags default off — operators opt-in once the credentials are
    # in env. Models are env-overridable so a Wiro slug change
    # ("qwen3-6-27b" → "qwen3-7b" etc.) doesn't need a code release.

    # Qwen3.6-27B — text generation (quote summary, doctor-Q&A drafts).
    WIRO_QWEN_LLM_ENABLED: bool = False
    WIRO_QWEN_LLM_MODEL: str = "qwen/qwen3-6-27b"

    # Whisper-large-v3-turbo-turkish — speech-to-text (multilingual
    # patient voice intake). Optimised for Turkish; auto-detects
    # 50+ languages.
    WIRO_WHISPER_STT_ENABLED: bool = False
    WIRO_WHISPER_STT_MODEL: str = "openai/whisper-large-v3-turbo-turkish"

    # CogVLM2-LLaMA3 — video-to-text caption (visual assessment of
    # hair / smile / skin clips). Domain-tuned prompt presets in
    # services/ai/cogvlm_caption.py::HEALTH_TOURISM_PROMPTS.
    WIRO_COGVLM_CAPTION_ENABLED: bool = False
    WIRO_COGVLM_CAPTION_MODEL: str = "thudm/cogvlm2-llama3-caption"

    # Google Gemini-3-Pro — multimodal LLM (text + up to 50 mixed
    # files: images / videos / audio in one call). Different from
    # Qwen LLM: native multimodal, thinking_level dial. Use for
    # quote summaries that consume profile + procedure + clinic +
    # patient-uploaded files in one shot. NOTE: every service in
    # app/services/ai/* requires WIRO_API_SECRET (HMAC signature
    # auth) — the wiro_client.require_signature_auth() guard will
    # fail-loud at submit time if it's empty.
    WIRO_GEMINI_LLM_ENABLED: bool = False
    WIRO_GEMINI_LLM_MODEL: str = "google/gemini-3-pro"

    # Moondream3-Preview — visual Q&A on a single image with
    # optional reasoning trace. Faster + cheaper than CogVLM2 video
    # caption when motion isn't needed (selfie / smile / scalp
    # photos). Domain-tuned prompt presets in
    # services/ai/moondream_vlm.py::HEALTH_TOURISM_PROMPTS.
    WIRO_MOONDREAM_VLM_ENABLED: bool = False
    WIRO_MOONDREAM_VLM_MODEL: str = "moondream3-preview/query"

    # nano-banana-pro — Google's text-to-image / image-edit model.
    # Output: list of CDN URLs (PNG). Use case: marketing collateral,
    # before/after illustrations for clinic comparison flows. NOT for
    # patient-facing medical visualizations (legal liability).
    WIRO_NANO_BANANA_IMAGE_ENABLED: bool = False
    WIRO_NANO_BANANA_IMAGE_MODEL: str = "google/nano-banana-pro"

    # gpt-image-2 — OpenAI's image gen/edit with optional inpaint mask.
    # Output: list of CDN URLs. Use case: same as nano-banana but with
    # inpainting (fill a masked region while keeping the rest of the
    # image identical) — handy for "subtle whitening" or localised
    # cosmetic edit mockups.
    WIRO_GPT_IMAGE_ENABLED: bool = False
    WIRO_GPT_IMAGE_MODEL: str = "openai/gpt-image-2"

    # gpt-5-mini — cheaper text+image LLM. Use case: short summaries,
    # routine clinic Q&A drafts. No temperature/topP/maxOutputTokens
    # knobs (per Wiro schema); reasoning + verbosity instead.
    WIRO_GPT5_MINI_LLM_ENABLED: bool = False
    WIRO_GPT5_MINI_LLM_MODEL: str = "openai/gpt-5-mini"

    # grok-4-20 — xAI's text+image LLM with full sampling controls
    # (temperature, topP, maxOutputTokens). Use case: long-form quote
    # summary alternative to Gemini-3-Pro when a different vendor's
    # tone is preferred or for vendor-redundancy in production.
    WIRO_GROK_LLM_ENABLED: bool = False
    WIRO_GROK_LLM_MODEL: str = "xai/grok-4-20"

    # dots-ocr-1-5 — multi-document OCR / layout extraction. Use case:
    # patient lab results / prescriptions / prior surgery records. The
    # ``promptMode`` enum picks layout style (full, layout-only, plain
    # OCR, web parsing, scene text). Output is JSON-structured layout.
    WIRO_DOTS_OCR_ENABLED: bool = False
    WIRO_DOTS_OCR_MODEL: str = "kristaller486/dots-ocr-1-5"

    # ── Health-tourism: LLM-generated quote summary ──────────────────────
    # Optional patient-facing 2-3 sentence Turkish blurb explaining why
    # the top-1 clinic ranked first. Generated **out-of-band** via
    # FastAPI BackgroundTasks because Wiro task latency (5-30s) is too
    # long to inline in the /v1/quote response without blowing the p95
    # SLO. UX contract: first request returns ``summary_tr=None``;
    # subsequent /v1/quote calls (same procedure / city / locale) hit
    # the in-memory LRU cache and surface the generated text.
    #
    # Provider chain is comma-separated, primary first. Each provider's
    # ``is_enabled()`` is checked at call site — disabled providers
    # are skipped, the chain advances. If all providers fail / are
    # disabled, the field stays ``None``.
    QUOTE_SUMMARY_LLM_ENABLED: bool = False
    # Default chain order: qwen (Türkçe-tuned, primary) -> gemini
    # (262K-context multimodal, robust fallback) -> gpt5_mini (cheaper
    # last-resort for short summaries). All three must have their own
    # WIRO_*_ENABLED flag on AND a valid WIRO_API_SECRET; the chain
    # walker silently skips disabled providers.
    QUOTE_SUMMARY_LLM_PROVIDERS: str = "qwen,gemini,gpt5_mini"
    # Wall-clock budget for ONE provider's submit+poll. The full chain
    # may take up to len(providers) * timeout in the worst case — but
    # since this runs in a background task, that's a cost concern, not
    # a UX one.
    QUOTE_SUMMARY_LLM_TIMEOUT_SECONDS: float = 30.0
    QUOTE_SUMMARY_CACHE_TTL_SECONDS: int = 86400  # 24 h
    QUOTE_SUMMARY_CACHE_MAX_ENTRIES: int = 256

    # ── Dashboard operators: per-user API key + rate limit ──────────────
    # Operators authenticate with x-operator-key (sha256-hashed at the
    # operator_users table). Each operator has its own bucket so a
    # noisy operator can't deny others. ADMIN_API_KEY (super-admin)
    # bypasses the operator bucket and uses the existing admin bucket.
    OPERATOR_RATE_LIMIT_WINDOW_SEC: int = 60
    OPERATOR_RATE_LIMIT_MAX_REQ: int = 60

    # ── Health-tourism: patient upload + AI dispatcher ───────────────────
    # Master flag for /v1/patient/upload — when False the route returns
    # 503; lets operators turn off the entire upload surface during
    # incident response without redeploying.
    PATIENT_UPLOAD_ENABLED: bool = False

    # Retention. After this many days, a nightly cron (future) will
    # tombstone the row in the same shape data_rights uses. AI result
    # text is the only patient-derivable content held; cleared on
    # tombstone.
    PATIENT_UPLOAD_RETENTION_DAYS: int = 30

    # Per-kind size caps (bytes). Selfie / dental / scalp photos sit
    # comfortably under 10MB; voice memos under 25MB; clinical clips
    # need headroom for 4K/30s; lab scans rarely exceed 10MB. The
    # route validates kind + content_type + size before hashing so
    # malicious 1GB uploads bail at the boundary.
    PATIENT_UPLOAD_MAX_IMAGE_BYTES: int = 10 * 1024 * 1024
    PATIENT_UPLOAD_MAX_AUDIO_BYTES: int = 25 * 1024 * 1024
    PATIENT_UPLOAD_MAX_VIDEO_BYTES: int = 100 * 1024 * 1024
    PATIENT_UPLOAD_MAX_DOCUMENT_BYTES: int = 10 * 1024 * 1024

    # Polling: how long between status checks the client should wait.
    # Surfaces in GET /v1/patient/upload/{asset_id} as a hint header
    # so naive clients don't hammer the endpoint.
    PATIENT_UPLOAD_POLL_INTERVAL_SECONDS: int = 5

    # ── Health-tourism: lead conversion webhook ──────────────────────────
    # When LEAD_WEBHOOK_URL is set, /v1/quote/lead dispatches a JSON
    # POST after accepting the lead. Compatible with Slack incoming
    # webhooks, Make/Zapier hooks, and any generic HTTP receiver. The
    # endpoint stays synchronous from the caller's perspective; the
    # dispatch happens in a background task with bounded retries so
    # one slow CRM doesn't add seconds to user-facing latency.
    LEAD_WEBHOOK_URL: str = ""
    LEAD_WEBHOOK_AUTH_TOKEN: str = ""  # sent as 'Authorization: Bearer ...'
    LEAD_WEBHOOK_TIMEOUT_SECONDS: float = 5.0
    LEAD_WEBHOOK_MAX_RETRIES: int = 3

    # ── Curated injection score tiers (audit follow-up) ──────────────────
    # triage_engine.py used to hardcode per-injection score_0_1 values
    # scattered across 25+ call sites. They collapse into three tiers.
    # Ops can tune these without a code release; the percentage shown
    # in the mobile UI and the RESULT envelope derives from these.
    #
    #   HIGH   — core curated categories where the canonical pattern
    #             maps 1:1 to the clinical label (panic attack,
    #             otitis, bronchiolitis, renal colic, dysmenorrhea,
    #             PCOS, conjunctivitis).
    #   MEDIUM — strong signal but multi-label (migraine, diabetes,
    #             hypertension, hypothyroid, ENT/derm/GI categories).
    #   LOW    — lifecycle or less-specific (prenatal follow-up,
    #             menopause, cataract, stye, frozen shoulder,
    #             lumbar-pain / sciatica, knee injury).
    CURATED_INJECTION_SCORE_HIGH: float = 0.70
    CURATED_INJECTION_SCORE_MEDIUM: float = 0.60
    CURATED_INJECTION_SCORE_LOW: float = 0.55

    # ── HTTP 5xx health alerts (post-C3 observability) ───────────────────
    # Rolling-window 5xx rate; same design as LLM health monitor.
    HTTP_5XX_ALERT_ENABLED: bool = True
    HTTP_5XX_ALERT_WINDOW: int = 50
    HTTP_5XX_ALERT_MIN_REQS: int = 20
    HTTP_5XX_ALERT_SUCCESS_THRESHOLD_PCT: float = 95.0  # <95% success → alert
    HTTP_5XX_ALERT_COOLDOWN_SEC: int = 600  # 10 minutes

    # ── LLM health alerts (post-C3 observability) ────────────────────────
    # When the rolling-window LLM success rate drops below
    # LLM_HEALTH_ALERT_THRESHOLD_PCT, notifier.py posts a webhook alert
    # to Slack/Discord (if configured). Only fires once per
    # LLM_HEALTH_ALERT_COOLDOWN_SEC to avoid storm-on-outage.
    LLM_HEALTH_ALERT_ENABLED: bool = True
    LLM_HEALTH_ALERT_WINDOW: int = 20        # rolling-window size (# calls)
    LLM_HEALTH_ALERT_MIN_CALLS: int = 5      # require this many observations before evaluating
    LLM_HEALTH_ALERT_THRESHOLD_PCT: float = 80.0
    LLM_HEALTH_ALERT_COOLDOWN_SEC: int = 900  # 15 minutes

    # ── RESULT envelope top_conditions gate (C2) ──────────────────────────
    # Below this confidence, Kaggle-derived disease candidates are dropped
    # from the RESULT envelope's top_conditions. Curated entries (Panik
    # Bozukluk, Majör Depresyon, Bronşiolit, Akut Otitis Media, Renal
    # Kolik, Dismenore, PCOS, Alerjik Konjonktivit) are exempt — they
    # come from deterministic canonical patterns, not fragile score
    # overlaps. Tune this against user feedback on the confidence-
    # indicator quality. 0.00 disables the gate entirely (all Kaggle
    # candidates surface); 1.00 drops all Kaggle candidates regardless
    # of confidence. Typical live scenarios sit in 0.09–0.50.
    RESULT_TOP_CONDITIONS_GATE: float = 0.25

    # ── Mobile client version enforcement (M4) ────────────────────────────
    # Surfaced via /v1/config/features. The mobile app reads this on
    # startup and compares against its own app.version (expo-constants).
    #
    # enforcement_mode semantics:
    #   "off"   — ignore version mismatches (default for dev)
    #   "warn"  — show a non-blocking banner asking user to update
    #   "block" — refuse to proceed, send user to the app-store link
    #
    # Rolled as a feature flag rather than a hard-fail semantic so ops
    # can flip "block" on only after a bake period on "warn". Also
    # lets a single field-fix release ship with enforcement off while
    # a separate release ships "block" for anyone still on the prior
    # broken version.
    MIN_CLIENT_VERSION: str = "0.0.0"         # below this → treated as out-of-date
    LATEST_CLIENT_VERSION: str = "0.0.0"      # informational, surfaced to the UI
    CLIENT_VERSION_ENFORCEMENT: str = "off"   # "off" | "warn" | "block"
    CLIENT_VERSION_UPDATE_URL_IOS: str = ""   # optional app-store deep link
    CLIENT_VERSION_UPDATE_URL_ANDROID: str = ""

    # ── Rate-limit rejection monitor (Session 4) ─────────────────────────
    # Rolling-window observer fires a webhook when the rate-limit
    # rejection rate (per decision, across all buckets) exceeds a
    # threshold. Same shape as LLM_HEALTH_ALERT_* and HTTP_5XX_ALERT_*:
    # min_decisions gate, cool-down to avoid storm-on-abuse, disable-
    # able via the _ENABLED flag. Fires one INFO line per alert so ops
    # can distinguish "real abuse" vs "legit traffic spike" without
    # staring at logs.
    RATE_LIMIT_ALERT_ENABLED: bool = True
    RATE_LIMIT_ALERT_WINDOW: int = 100          # last N rate-limit decisions
    RATE_LIMIT_ALERT_MIN_DECISIONS: int = 30    # require this many before evaluating
    RATE_LIMIT_ALERT_THRESHOLD_PCT: float = 10.0  # >10% rejected → alert
    RATE_LIMIT_ALERT_COOLDOWN_SEC: int = 600    # 10 minutes between pages

    # ── Sentry error aggregation ─────────────────────────────────────────
    # If SENTRY_DSN is empty, sentry_sdk.init() is a no-op — the app
    # runs unchanged without an external dep. Set the DSN + environment
    # in prod to enable error tracking; traces_sample_rate controls
    # perf-trace sampling (0 = no traces, 1 = every request — costly).
    # PII scrubbing is applied in a before_send hook (see app/main.py).
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0   # default: error-only, no perf
    SENTRY_RELEASE: str = ""                 # blank → let SDK auto-detect

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
