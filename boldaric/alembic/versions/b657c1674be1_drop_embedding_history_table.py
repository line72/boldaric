"""drop embedding_history table

Revision ID: b657c1674be1
Revises: aafc0e5c01f8
Create Date: 2025-11-16 14:57:05.715836

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b657c1674be1"
down_revision: Union[str, None] = "aafc0e5c01f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop embedding_history table completely
    op.drop_table("embedding_history")


def downgrade() -> None:
    # Recreate embedding_history table
    op.create_table(
        "embedding_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("station_id", sa.Integer(), nullable=False),
        sa.Column("track_history_id", sa.Integer(), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["station_id"],
            ["stations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["track_history_id"],
            ["track_history.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
