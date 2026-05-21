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
    # Render provides postgresql:// — we convert to asyncpg for the app
    # and keep sync version for Alembic
    database_url: str
    sync_database_url: str | None = None

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    @property
    def async_database_url(self) -> str:
        """Always returns asyncpg-compatible URL for SQLAlchemy async engine."""
        url = self.database_url
        # Render gives postgresql:// or postgres:// — convert for asyncpg
        url = url.replace("postgres://", "postgresql+asyncpg://")
        url = url.replace("postgresql://", "postgresql+asyncpg://")
        return url

    @property
    def sync_db_url(self) -> str:
        """Always returns psycopg2-compatible URL for Alembic."""
        if self.sync_database_url:
            url = self.sync_database_url
        else:
            url = self.database_url
        # Strip asyncpg driver if present
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        url = url.replace("postgres://", "postgresql://")
        return url

    @property
    def api_prefix(self) -> str:
        return f"/api/{self.api_version}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()