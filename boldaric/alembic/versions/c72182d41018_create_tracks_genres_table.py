"""create_tracks_genres_table

Revision ID: c72182d41018
Revises: 114385708a78
Create Date: 2025-10-26 10:29:41.028169

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c72182d41018'
down_revision: Union[str, None] = '114385708a78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tracks_genres",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("genre_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.REAL()),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["genre_id"], ["genres.id"], ondelete="CASCADE")
    )

    op.create_index(
        op.f("ix_unique_tracks_genres"), "tracks_genres", ["track_id", "genre_id"], unique=True
    )


def downgrade() -> None:
    # Drop index first
    op.drop_index(op.f("ix_unique_tracks_genres"), table_name="tracks_genres")

    # Drop table
    op.drop_table("tracks_genres")

