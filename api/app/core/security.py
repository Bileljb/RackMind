import hmac
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

# Argon2 is the current recommended password hashing algorithm.
_password_hash = PasswordHash.recommended()

# Name of the httpOnly cookie that holds the login token. The web app's `proxy.ts` checks it.
SESSION_COOKIE = "rackmind_session"
_JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _password_hash.verify(password, hashed)


@lru_cache
def dummy_password_hash() -> str:
    """A real hash to verify against when the email is unknown.

    Login then takes the same time whether or not the account exists, so response times
    don't reveal which emails are registered.
    """
    return hash_password("not-a-real-password")


def create_access_token(user_id: int) -> str:
    """A signed JWT saying "this is user N" until it expires.

    The role is deliberately not in the token: it is read from the database on every request,
    so a role change or deactivation applies immediately, not when the token expires.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.session_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=_JWT_ALGORITHM)


def read_access_token(token: str) -> int | None:
    """The user id in a valid token, or None if it is forged, expired or malformed."""
    secret = get_settings().jwt_secret.get_secret_value()
    try:
        claims = jwt.decode(
            token, secret, algorithms=[_JWT_ALGORITHM], options={"require": ["exp", "sub"]}
        )
        return int(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None


def is_valid_ingest_key(key: str) -> bool:
    # compare_digest takes the same time however many characters match, so the key can't be
    # guessed one character at a time by measuring response times.
    expected = get_settings().ingest_api_key.get_secret_value()
    return hmac.compare_digest(key.encode(), expected.encode())
