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

    # Multi-tenant dataset config
    # Default tenant id (used when header / key'den tenant çözülemez)
    DEFAULT_TENANT_ID: str = "default"
    # JSON object: { "admin_api_key_value": "tenant_id", ... }
    TENANT_ADMIN_KEYS_JSON: str = "{}"
    # JSON array: ["tenant_id_1", "tenant_id_2", ...] — public triage için izin verilen tenant listesi
    TENANT_ALLOWLIST_JSON: str = "[]"
    # Dataset kök klasörü (her tenant için alt klasör)
    DATASETS_ROOT: str = "backend/data_sets"
    # Tenant-bazlı config kökü (emergency_rules.json, risk_rules.json, vb.)
    TENANT_CONFIG_ROOT: str = "config"

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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
