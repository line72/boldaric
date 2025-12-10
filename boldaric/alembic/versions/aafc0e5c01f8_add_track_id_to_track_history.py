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
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table("track_history") as batch_op:
        # Add track_id column as nullable first
        batch_op.add_column(sa.Column("track_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_track_history_tracks", "tracks", ["track_id"], ["id"]
        )

        # Add rating column to track_history
        batch_op.add_column(sa.Column("rating", sa.Integer(), nullable=True, default=0))

        batch_op.drop_index("idx_unique_station_subsonic")

        # Drop redundant columns
        batch_op.drop_column("artist")
        batch_op.drop_column("title")
        batch_op.drop_column("album")
        batch_op.drop_column("subsonic_id")


def downgrade() -> None:
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table("track_history") as batch_op:
        # Re-add dropped columns
        batch_op.add_column(sa.Column("subsonic_id", sa.VARCHAR(), nullable=False))
        batch_op.add_column(
            "track_history", sa.Column("album", sa.VARCHAR(), nullable=False)
        )
        batch_op.add_column(
            "track_history", sa.Column("title", sa.VARCHAR(), nullable=False)
        )
        batch_op.add_column(
            "track_history", sa.Column("artist", sa.VARCHAR(), nullable=False)
        )

        # Remove rating column from track_history
        batch_op.drop_column("rating")

        # Drop foreign key and track_id column
        batch_op.drop_constraint("fk_track_history_tracks", type_="foreignkey")
        batch_op.drop_column("track_id")
