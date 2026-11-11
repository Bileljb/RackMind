from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
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

    # Signs login tokens: anyone who knows it can forge a session. Long and random, never in git.
    jwt_secret: SecretStr = Field(min_length=32)
    session_minutes: int = Field(default=8 * 60, gt=0)  # one work shift, then log in again
    # Send the session cookie over HTTPS only. Off for local http://localhost, on in production.
    cookie_secure: bool = False
    # Shared secret the simulator sends in `X-API-Key` to push metrics (it is not a user).
    ingest_api_key: SecretStr = Field(min_length=16)

    # AI diagnosis (Groq). No key = the feature is off and incidents say so; nothing else breaks.
    groq_api_key: SecretStr | None = None
    groq_model: str = Field(default="openai/gpt-oss-120b", min_length=1)
    groq_timeout_s: float = Field(default=30, gt=0)  # per attempt
    groq_max_retries: int = Field(default=3, ge=0)  # on timeouts, 429 and 5xx, with backoff

    # A real server with no reading for this long gets a "not reporting" incident. Agents send
    # every 5s, so 60s means about 12 missed readings: a dead machine, not a slow request.
    heartbeat_timeout_s: int = Field(default=60, ge=15)


@lru_cache
def get_settings() -> Settings:
    """Return the settings, built once and reused (cached) for the life of the process."""
    return Settings()
