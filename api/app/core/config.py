from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables (and `.env` if present).

    Field names map to env vars case-insensitively: `database_url` <- `DATABASE_URL`.
    Fields without a default are required: the app refuses to start if they are missing.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Rackmind"
    environment: Literal["development", "test", "production"] = "development"
    database_url: PostgresDsn
    redis_url: RedisDsn
    # Only needed by the seed script; SecretStr hides the value in logs and reprs.
    seed_password: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the settings, built once and reused (cached) for the life of the process."""
    return Settings()
