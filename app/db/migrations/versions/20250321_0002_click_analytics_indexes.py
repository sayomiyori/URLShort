"""partial indexes for stats aggregates

Revision ID: 0002
Revises: 0001
Create Date: 2025-03-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_click_url_country_partial",
        "click",
        ["url_id", "country"],
        unique=False,
        postgresql_where=sa.text("country IS NOT NULL"),
    )
    op.create_index(
        "ix_click_url_referer_partial",
        "click",
        ["url_id", "referer"],
        unique=False,
        postgresql_where=sa.text("referer IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_click_url_referer_partial", table_name="click")
    op.drop_index("ix_click_url_country_partial", table_name="click")
