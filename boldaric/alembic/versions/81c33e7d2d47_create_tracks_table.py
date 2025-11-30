"""create_tracks_table

Revision ID: 81c33e7d2d47
Revises: 976eefd09ec2
Create Date: 2025-10-26 07:47:55.388014

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "81c33e7d2d47"
down_revision: Union[str, None] = "976eefd09ec2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tracks table
    op.create_table(
        "tracks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("artist", sa.String),
        sa.Column("album", sa.String),
        sa.Column("track", sa.String),
        sa.Column("track_number", sa.Integer),
        sa.Column("genre", sa.String),
        sa.Column("subsonic_id", sa.String, nullable=False),
        sa.Column("musicbrainz_artistid", sa.String),
        sa.Column("musicbrainz_albumid", sa.String),
        sa.Column("musicbrainz_trackid", sa.String),
        sa.Column("releasetype", sa.String),
        sa.Column("releasestatus", sa.String),
        sa.Column("genre_embedding", sa.LargeBinary),
        sa.Column("mfcc_covariance", sa.LargeBinary),
        sa.Column("mfcc_mean", sa.LargeBinary),
        sa.Column("mfcc_temporal_variation", sa.REAL),
        sa.Column("bpm", sa.REAL),
        sa.Column("loudness", sa.REAL),
        sa.Column("dynamic_complexity", sa.REAL),
        sa.Column("energy_curve_mean", sa.REAL),
        sa.Column("energy_curve_std", sa.REAL),
        sa.Column("energy_curve_peak_count", sa.Integer),
        sa.Column("key_tonic", sa.String),
        sa.Column("key_scale", sa.String),
        sa.Column("key_confidence", sa.REAL),
        sa.Column("chord_unique_chords", sa.Integer),
        sa.Column("chord_change_rate", sa.REAL),
        sa.Column("vocal_pitch_presence_ratio", sa.REAL),
        sa.Column("vocal_pitch_segment_count", sa.Integer),
        sa.Column("vocal_avg_pitch_duration", sa.REAL),
        sa.Column("groove_beat_consistency", sa.REAL),
        sa.Column("groove_danceability", sa.REAL),
        sa.Column("groove_dnc_bpm", sa.REAL),
        sa.Column("groove_syncopation", sa.REAL),
        sa.Column("groove_tempo_stability", sa.REAL),
        sa.Column("mood_aggressiveness", sa.REAL),
        sa.Column("mood_happiness", sa.REAL),
        sa.Column("mood_partiness", sa.REAL),
        sa.Column("mood_relaxedness", sa.REAL),
        sa.Column("mood_sadness", sa.REAL),
        sa.Column("spectral_character_brightness", sa.REAL),
        sa.Column("spectral_character_contrast_mean", sa.REAL),
        sa.Column("spectral_character_valley_std", sa.REAL),
        sa.Column("created_at", sa.DateTime, default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime, default=sa.func.now(), onupdate=sa.func.now()
        ),
    )

    # Create unique index on subsonic_id for fast & unique lookups
    op.create_index(
        op.f("ix_tracks_subsonic_id"), "tracks", ["subsonic_id"], unique=True
    )


def downgrade() -> None:
    # Drop index first
    op.drop_index(op.f("ix_tracks_subsonic_id"), table_name="tracks")

    # Drop table
    op.drop_table("tracks")
