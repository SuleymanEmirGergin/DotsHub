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
    # JSON array of allowed CORS origins. In production set explicitly to your app/dashboard URLs.
    CORS_ORIGINS: str = '["http://localhost:8081","http://localhost:19006","http://localhost:3000"]'
    ADMIN_API_KEY: str = ""

    # Webhook notifications
    WEBHOOK_ENABLED: bool = False
    WEBHOOK_SLACK_URL: str = ""
    WEBHOOK_DISCORD_URL: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.CORS_ORIGINS)

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
