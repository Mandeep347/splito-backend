from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Splito"
    api_version: str = "v1"
    debug: bool = False
    app_env: str = "development"

    # Database
    database_url: str
    sync_database_url: str | None = None

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Email — Resend
    resend_api_key: str = ""
    email_from_verify: str = "verify@support.splitmate.page"
    email_from_reset: str = "security@support.splitmate.page"
    frontend_url: str = "http://localhost:3000"

    # Token expiry
    email_verification_expire_hours: int = 24
    password_reset_expire_minutes: int = 15

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        url = url.replace("postgres://", "postgresql://")
        if "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://")
        return url

    @property
    def sync_db_url(self) -> str:
        if self.sync_database_url:
            url = self.sync_database_url
        else:
            url = self.database_url
        url = url.replace("postgres://", "postgresql://")
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        return url

    @property
    def api_prefix(self) -> str:
        return f"/api/{self.api_version}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
