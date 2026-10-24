from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:  # imported only for type hints, avoids a circular import at runtime
    from app.models.server import Server


class Rack(TimestampMixin, Base):
    __tablename__ = "racks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    location: Mapped[str] = mapped_column(String(100))

    servers: Mapped[list["Server"]] = relationship(back_populates="rack")
