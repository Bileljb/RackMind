"""Accounts: login check and admin user management. There is no public sign-up."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import dummy_password_hash, hash_password, verify_password
from app.models import Role, User
from app.schemas.user import UserCreate, UserUpdate
from app.services.audit import record_event


class EmailTakenError(Exception):
    pass


class SelfLockoutError(Exception):
    """An admin tried to demote or deactivate their own account."""


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    """The active user with these credentials, or None. Same answer for every kind of failure."""
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(password, dummy_password_hash())  # spend the same time as a real check
        return None
    if not verify_password(password, user.hashed_password) or not user.is_active:
        return None
    return user


async def list_users(db: AsyncSession) -> list[User]:
    return list(await db.scalars(select(User).order_by(User.id)))


async def create_user(db: AsyncSession, data: UserCreate, actor: User) -> User:
    if await db.scalar(select(User.id).where(User.email == data.email)) is not None:
        raise EmailTakenError
    user = User(
        email=data.email,
        full_name=data.full_name,
        role=data.role,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.flush()  # get the new id for the audit entry
    record_event(db, "user", user.id, "user.created", actor, email=user.email, role=user.role)
    await db.commit()
    await db.refresh(user)  # load `created_at`, filled in by Postgres
    return user


async def update_user(db: AsyncSession, user: User, changes: UserUpdate, actor: User) -> User:
    if user.id == actor.id and (
        (changes.role is not None and changes.role is not Role.ADMIN) or changes.is_active is False
    ):
        raise SelfLockoutError

    changed: dict[str, object] = {}
    if changes.full_name is not None:
        user.full_name = changed["full_name"] = changes.full_name
    if changes.role is not None:
        user.role = changed["role"] = changes.role
    if changes.is_active is not None:
        user.is_active = changed["is_active"] = changes.is_active
    if changes.password is not None:
        user.hashed_password = hash_password(changes.password)
        changed["password"] = "reset"  # never log the password itself
    if changed:
        record_event(db, "user", user.id, "user.updated", actor, **changed)
        await db.commit()
    return user
