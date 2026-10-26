from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models import Role

# Stored lowercase so "Admin@x.io" and "admin@x.io" are the same account. The check is kept
# simple on purpose (one @, no spaces): demo addresses like `admin@rackmind.local` must pass.
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=255, pattern=r"^[^@\s]+@[^@\s]+$"
    ),
]
Password = Annotated[str, StringConstraints(min_length=10, max_length=128)]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class LoginIn(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True)]
    password: str


class UserOut(BaseModel):
    """A user as the API shows it: never the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime


class UserBrief(BaseModel):
    """What any logged-in user may see about colleagues: no email, no account dates."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    role: Role
    is_active: bool


class UserCreate(BaseModel):
    email: Email
    full_name: FullName
    role: Role
    password: Password


class UserUpdate(BaseModel):
    """Only the fields sent are changed (PATCH)."""

    full_name: FullName | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: Password | None = None
