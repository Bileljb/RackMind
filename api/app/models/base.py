from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable constraint names (e.g. `fk_servers_rack_id_racks`) so Alembic can find and
# alter/drop constraints later without guessing Postgres' auto-generated names.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Parent class of every model. Alembic reads `Base.metadata` to see all tables."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def enum_column(enum_cls: type[StrEnum]) -> Enum:
    """Column type storing a StrEnum's values (e.g. "open") as VARCHAR + a CHECK constraint.

    We avoid native Postgres ENUM types because adding/renaming values in later migrations
    is awkward; a CHECK constraint gives the same protection and is easy to change.
    """
    return Enum(
        enum_cls,
        name=enum_cls.__name__.lower(),
        native_enum=False,
        create_constraint=True,
        values_callable=lambda members: [m.value for m in members],
    )


class TimestampMixin:
    """Adds a `created_at` column filled in by Postgres at insert time."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
