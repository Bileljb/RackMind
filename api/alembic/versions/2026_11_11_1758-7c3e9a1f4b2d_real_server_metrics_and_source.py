"""real server metrics and server source

Revision ID: 7c3e9a1f4b2d
Revises: ec550a63b9d6
Create Date: 2026-11-11 17:58:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c3e9a1f4b2d"
down_revision: str | None = "ec550a63b9d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Real servers (VPSes) have no temperature or power sensors.
    op.alter_column("metrics", "cpu_temp", existing_type=sa.Float(), nullable=True)
    op.alter_column("metrics", "power_w", existing_type=sa.Float(), nullable=True)
    # Nullable: old rows were recorded before this metric existed.
    op.add_column("metrics", sa.Column("cpu_usage_pct", sa.Float(), nullable=True))

    # The server_default fills existing rows (all 20 are simulated) in the same statement.
    op.add_column(
        "servers",
        sa.Column(
            "source",
            sa.Enum(
                "simulated",
                "agent",
                name="serversource",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="simulated",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("servers", "source")
    op.drop_column("metrics", "cpu_usage_pct")
    # Fails if readings without temperature or power exist: delete agent readings first.
    op.alter_column("metrics", "power_w", existing_type=sa.Float(), nullable=False)
    op.alter_column("metrics", "cpu_temp", existing_type=sa.Float(), nullable=False)
