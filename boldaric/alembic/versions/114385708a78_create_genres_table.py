"""create_genres_table

Revision ID: 114385708a78
Revises: 81c33e7d2d47
Create Date: 2025-10-26 10:26:22.317239

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "114385708a78"
down_revision: Union[str, None] = "81c33e7d2d47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "genres",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("label", sa.String),
    )

    op.create_index(op.f("ix_genres_label"), "genres", ["label"], unique=True)


def downgrade() -> None:
    # Drop the index first
    op.drop_index(op.f("ix_genres_label"), table_name="genres")

    # Drop table
    op.drop_table("genres")
