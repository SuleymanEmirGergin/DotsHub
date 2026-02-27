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

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.CORS_ORIGINS)

    # Agent config
    MAX_QUESTIONS: int = 6
    TEMPERATURE: float = 0.3

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
