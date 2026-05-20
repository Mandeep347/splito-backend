from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",   # ignore postgres_user, postgres_host etc. used only by Docker
    )

    # App
    app_name: str = "Splito"
    api_version: str = "v1"
    debug: bool = False
    app_env: str = "development"

    # Database
    database_url: str
    sync_database_url: str | None = None  # used by Alembic CLI; auto-derived if not set

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    @property
    def api_prefix(self) -> str:
        return f"/api/{self.api_version}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
