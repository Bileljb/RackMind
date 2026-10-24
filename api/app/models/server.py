from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.rack import Rack


class Server(TimestampMixin, Base):
    __tablename__ = "servers"
    # Two servers can't occupy the same slot in the same rack.
    __table_args__ = (UniqueConstraint("rack_id", "rack_unit", name="uq_servers_rack_slot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    rack_id: Mapped[int] = mapped_column(ForeignKey("racks.id", ondelete="CASCADE"), index=True)
    hostname: Mapped[str] = mapped_column(String(100), unique=True)
    rack_unit: Mapped[int]  # vertical slot in the rack (U1 at the bottom)

    rack: Mapped["Rack"] = relationship(back_populates="servers")
