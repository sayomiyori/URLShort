"""initial schema

Revision ID: 0001
Revises:
Create Date: 2025-03-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "url",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("short_code", sa.String(length=64), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("custom_alias", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("click_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("owner_api_key", sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_url_created_at", "url", ["created_at"], unique=False)
    op.create_index("ix_url_short_code", "url", ["short_code"], unique=True)

    op.create_table(
        "click",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("url_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "clicked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=False),
        sa.Column("referer", sa.Text(), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("device_type", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["url_id"], ["url.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_click_url_id_clicked_at",
        "click",
        ["url_id", "clicked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_click_url_id_clicked_at", table_name="click")
    op.drop_table("click")
    op.drop_index("ix_url_short_code", table_name="url")
    op.drop_index("ix_url_created_at", table_name="url")
    op.drop_table("url")
