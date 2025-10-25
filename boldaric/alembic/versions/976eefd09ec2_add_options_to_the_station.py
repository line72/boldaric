"""add options to the station

Revision ID: 976eefd09ec2
Revises: initial
Create Date: 2025-09-21 09:16:15.584993

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '976eefd09ec2'
down_revision: Union[str, None] = 'initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add several new options to the stations table
    
    op.add_column('stations', sa.Column('replay_song_cooldown', sa.Integer(), nullable=True, default=50))
    op.add_column('stations', sa.Column('replay_artist_downrank', sa.Float(), nullable=True, default=0.995))
    op.add_column('stations', sa.Column('ignore_live', sa.Boolean(), nullable=True, default=False))
    
    # Set default values for existing rows
    op.execute("UPDATE stations SET replay_song_cooldown = 50 WHERE replay_song_cooldown IS NULL")
    op.execute("UPDATE stations SET replay_artist_downrank = 0.995 WHERE replay_artist_downrank IS NULL")
    op.execute("UPDATE stations SET ignore_live = 0 WHERE ignore_live IS NULL")


def downgrade() -> None:
    op.drop_column('stations', 'ignore_live')
    op.drop_column('stations', 'replay_artist_downrank')
    op.drop_column('stations', 'replay_song_cooldown')
             
