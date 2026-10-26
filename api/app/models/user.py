from enum import StrEnum

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, enum_column


class Role(StrEnum):
    OPERATOR = "operator"
    ENGINEER = "engineer"
    ADMIN = "admin"

    @property
    def rank(self) -> int:
        """0, 1, 2: each role can do everything the roles below it can."""
        return list(Role).index(self)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(enum_column(Role))
    is_active: Mapped[bool] = mapped_column(default=True)
