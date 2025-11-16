"""add_track_id_to_track_history

Revision ID: aafc0e5c01f8
Revises: c72182d41018
Create Date: 2025-11-16 14:47:55.460613

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "aafc0e5c01f8"
down_revision: Union[str, None] = "c72182d41018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add track_id column as nullable first
    op.add_column("track_history", sa.Column("track_id", sa.Integer(), nullable=True))
    op.create_foreign_key(None, "track_history", "tracks", ["track_id"], ["id"])

    # Add rating column to track_history
    op.add_column(
        "track_history", sa.Column("rating", sa.Integer(), nullable=True, default=0)
    )

    # Drop redundant columns
    op.drop_column("track_history", "artist")
    op.drop_column("track_history", "title")
    op.drop_column("track_history", "album")
    op.drop_column("track_history", "subsonic_id")


def downgrade() -> None:
    # Re-add dropped columns
    op.add_column(
        "track_history", sa.Column("subsonic_id", sa.VARCHAR(), nullable=False)
    )
    op.add_column("track_history", sa.Column("album", sa.VARCHAR(), nullable=False))
    op.add_column("track_history", sa.Column("title", sa.VARCHAR(), nullable=False))
    op.add_column("track_history", sa.Column("artist", sa.VARCHAR(), nullable=False))

    # Remove rating column from track_history
    op.drop_column("track_history", "rating")

    # Drop foreign key and track_id column
    op.drop_constraint(None, "track_history", type_="foreignkey")
    op.drop_column("track_history", "track_id")
