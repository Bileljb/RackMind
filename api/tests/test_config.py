import pytest

from app.core.config import Settings


def _database_url(value: str) -> str:
    settings = Settings.model_validate(
        {
            "database_url": value,
            "redis_url": "redis://localhost:6379/0",
            "jwt_secret": "x" * 32,
            "ingest_api_key": "y" * 16,
        }
    )
    return str(settings.database_url)


def test_neon_style_url_is_converted_for_asyncpg() -> None:
    url = _database_url(
        "postgresql://user:secret@ep-x.eu-central-1.aws.neon.tech/rackmind"
        "?sslmode=require&channel_binding=require"
    )

    assert url == (
        "postgresql+asyncpg://user:secret@ep-x.eu-central-1.aws.neon.tech/rackmind?ssl=require"
    )


@pytest.mark.parametrize(
    "value",
    ["postgres://u:p@db:5432/rackmind", "postgresql+asyncpg://u:p@db:5432/rackmind"],
)
def test_url_gets_the_asyncpg_driver(value: str) -> None:
    assert _database_url(value) == "postgresql+asyncpg://u:p@db:5432/rackmind"
