# Copyright (c) 2025 Marcus Dillavou <line72@line72.net>
# Part of the Boldaric Project:
#  https://github.com/line72/boldaric
# Released under the AGPLv3 or later

# Web Server for the boldaric project
#
# This provides a RESTful API for creating stations, getting next
# tracks for a stations, rating songs, seeding songs, and so on.

from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, timedelta
import numpy as np
import os

from importlib import resources

from . import simulator
from . import feature_helper
from .records.station_options import StationOptions

from alembic import command
from alembic.config import Config

from sqlalchemy import create_engine, and_, or_, func
from sqlalchemy.orm import sessionmaker, Session, joinedload

from .models.user import User
from .models.station import Station
from .models.track_history import TrackHistory
from .models.track import Track
from .models.genre import Genre
from .models.track_genre import TrackGenre


class StationDB:
    """
    A simple SQLite-based persistence layer for user stations and playback history.
    """

    def __init__(self, db_path: str = "stations.db"):
        self.db_path = db_path
        self._run_migrations()

        # Set up SQLAlchemy engine and session
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.Session = sessionmaker(bind=self.engine)

    def _run_migrations(self):
        """Run any pending database migrations."""
        # Check if database exists
        if not os.path.exists(self.db_path):
            # Create empty database file
            with open(self.db_path, "w") as f:
                pass

        # Run migrations
        alembic_ini_path = resources.files("boldaric").joinpath("alembic.ini")
        alembic_cfg = Config(str(alembic_ini_path))

        # Override script_location to be absolute
        alembic_dir = os.path.join(os.path.dirname(alembic_ini_path), "alembic")
        alembic_cfg.set_main_option("script_location", alembic_dir)
        alembic_cfg.set_main_option(
            "path_separator", os.pathsep
        )  # Fix for Alembic warning
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{self.db_path}")
        command.upgrade(alembic_cfg, "head")

    # ----------------------
    # User Management
    # ----------------------

    def create_user(self, username: str) -> int:
        """Create a new user and return their ID."""
        with self.Session() as session:
            user = User(username=username)
            session.add(user)
            session.commit()
            return user.id

    def get_user(self, username: str) -> Optional[User]:
        """Get a user by username."""
        with self.Session() as session:
            return session.query(User).filter(User.username == username).first()

    def get_all_users(self) -> List[User]:
        with self.Session() as session:
            return session.query(User).all()

    # ----------------------
    # Station Management
    # ----------------------

    def create_station(self, user_id: int, station_name: str) -> int:
        """Create a new station for a user."""
        with self.Session() as session:
            station = Station(user_id=user_id, name=station_name)
            session.add(station)
            session.commit()
            return station.id

    def get_stations_for_user(self, user_id: int) -> List[Station]:
        """Get all stations for a user."""
        with self.Session() as session:
            return session.query(Station).filter(Station.user_id == user_id).all()

    def get_station_id(self, user_id: int, station_name: str) -> Optional[int]:
        """Get a station ID by user ID and station name."""
        with self.Session() as session:
            station = (
                session.query(Station)
                .filter(Station.user_id == user_id, Station.name == station_name)
                .first()
            )
            return station.id if station else None

    def get_station(self, user_id: int, station_id: str) -> Optional[Station]:
        """Get a station by ID"""
        with self.Session() as session:
            return (
                session.query(Station)
                .filter(Station.user_id == user_id, Station.id == station_id)
                .first()
            )

    def get_station_options(self, station_id: int) -> StationOptions:
        """Get the options for a station"""
        with self.Session() as session:
            station = session.query(Station).filter(Station.id == station_id).first()
            if station:
                return StationOptions(
                    replay_song_cooldown=station.replay_song_cooldown,
                    replay_artist_downrank=station.replay_artist_downrank,
                    ignore_live=station.ignore_live,
                )
            # Fallback to default options if station not found
            return StationOptions()

    def set_station_options(
        self,
        station_id: int,
        replay_song_cooldown: int,
        replay_artist_downrank: float,
        ignore_live: bool,
    ) -> None:
        with self.Session() as session:
            station = session.query(Station).filter(Station.id == station_id).first()
            if station:
                station.replay_song_cooldown = replay_song_cooldown
                station.replay_artist_downrank = replay_artist_downrank
                station.ignore_live = ignore_live
                session.commit()

    def get_station_embedding(self, station_id: int) -> Optional[List[float]]:
        """Get the current embedding for a station."""
        with self.Session() as session:
            station = session.query(Station).filter(Station.id == station_id).first()
            if station and station.current_embedding:
                return station.current_embedding
        return None

    def set_station_embedding(self, station_id: int, embedding: List[float]) -> None:
        """Set the current embedding for a station."""
        with self.Session() as session:
            station = session.query(Station).filter(Station.id == station_id).first()
            if station:
                station.current_embedding = embedding
                session.commit()

    # ----------------------
    # History Management
    # ----------------------

    def add_track_to_or_update_history(
        self,
        station_id: int,
        track: Track,
        is_thumbs_downed: bool,
        rating: int = 0,
    ) -> int:
        """Add a track to the station's history. If it is recent, update the existing row"""
        with self.Session() as session:
            # Check if track already exists in history
            track_history = (
                session.query(TrackHistory)
                .filter(
                    TrackHistory.station_id == station_id,
                    TrackHistory.track_id == track.id,
                )
                .first()
            )

            if track_history:
                # Update existing record
                track_history.updated_at = datetime.now()
                # Only update thumbs_downed if it's being set to True
                if is_thumbs_downed:
                    track_history.is_thumbs_downed = is_thumbs_downed
                # Update rating if provided
                if rating != 0:
                    track_history.rating = rating
                session.commit()
                return track_history.id
            else:
                # Create new record
                track_history = TrackHistory(
                    track_id=track.id,
                    station_id=station_id,
                    is_thumbs_downed=is_thumbs_downed,
                    rating=rating,
                )
                session.add(track_history)
                session.commit()
                return track_history.id

    def get_track_history(self, station_id: int, limit: int = 20) -> List[TrackHistory]:
        """Get recent tracks played by a station."""
        with self.Session() as session:
            return (
                session.query(TrackHistory)
                .options(joinedload(TrackHistory.track))  # Eagerly load the track
                .filter(TrackHistory.station_id == station_id)
                .order_by(TrackHistory.updated_at.desc())
                .limit(limit)
                .all()
            )

    def get_track_history_all(self, station_id: int) -> List[TrackHistory]:
        """Get recent tracks played by a station."""
        with self.Session() as session:
            return (
                session.query(TrackHistory)
                .options(joinedload(TrackHistory.track))  # Eagerly load the track
                .filter(TrackHistory.station_id == station_id)
                .order_by(TrackHistory.updated_at.desc())
                .all()
            )

    def get_thumbs_downed_history(self, station_id: int) -> List[TrackHistory]:
        """Get all thumbs downed tracks by a station."""
        with self.Session() as session:
            return (
                session.query(TrackHistory)
                .options(joinedload(TrackHistory.track))  # Eagerly load the track
                .filter(
                    and_(
                        TrackHistory.station_id == station_id,
                        TrackHistory.is_thumbs_downed == True,
                    )
                )
                .order_by(TrackHistory.updated_at)
                .all()
            )

    def get_embedding_history(self, station_id: int) -> List[List[float]]:
        """Get embedding history for a station by fetching embeddings from tracks."""
        with self.Session() as session:
            # Get track history with associated tracks for this station
            track_histories = self.get_track_history_all(station_id)

            # Extract just the embeddings from the tracks
            history = simulator.make_history()
            for history_item in track_histories:
                # Get the embedding for this track
                embedding = feature_helper.track_to_embeddings(history_item.track)
                # Check that embedding has the right dimension (148)
                if len(embedding) == 148:
                    history = simulator.add_history(
                        history, embedding, history_item.rating
                    )

            return history

    # !mwd - TODO: This isn't currently used. Remove?
    def load_station_history(
        self, station_id: int
    ) -> Tuple[List[Any], List[TrackHistory], List[Dict[str, Any]]]:
        """Load embedding history, track history, and thumbs downed history for a station."""
        tracks = self.get_track_history_all(station_id)

        # Build history from embeddings
        history = simulator.make_history()
        for track_history in tracks:
            # Get the embedding for this track
            embedding = feature_helper.track_to_embeddings(track_history.track)
            # Check that embedding has the right dimension (148)
            if len(embedding) == 148:
                history = simulator.add_history(
                    history, embedding, track_history.rating
                )

        # Build thumbs downed from track history
        thumbs_downed = []
        with self.Session() as session:
            thumbs_downed_tracks = (
                session.query(TrackHistory)
                .filter(
                    and_(
                        TrackHistory.station_id == station_id,
                        TrackHistory.is_thumbs_downed == True,
                    )
                )
                .order_by(TrackHistory.created_at)
                .all()
            )

            thumbs_downed = [
                {
                    "metadata": {
                        "artist": track.artist,
                        "title": track.title,
                        "album": track.album,
                    }
                }
                for track in thumbs_downed_tracks
            ]

        return history, tracks, thumbs_downed

    # ----------------------
    # Track Management
    # ----------------------
    def add_track(
        self,
        artist: str,
        album: str,
        track: str,
        track_number: int,
        genre: str,
        subsonic_id: str,
        musicbrainz_artistid: str,
        musicbrainz_albumid: str,
        musicbrainz_trackid: str,
        releasetype: str,
        genre_list,
        genre_embedding,
        mfcc_covariance,
        mfcc_mean,
        mfcc_temporal_variation: float,
        bpm: float,
        loudness: float,
        dynamic_complexity: float,
        energy_curve_mean: float,
        energy_curve_std: float,
        energy_curve_peak_count: int,
        key_tonic: str,
        key_scale: str,
        key_confidence: float,
        chord_unique_chords: int,
        chord_change_rate: float,
        vocal_pitch_presence_ratio: float,
        vocal_pitch_segment_count: int,
        vocal_avg_pitch_duration: float,
        groove_beat_consistency: float,
        groove_danceability: float,
        groove_dnc_bpm: float,
        groove_syncopation: float,
        groove_tempo_stability: float,
        mood_aggressiveness: float,
        mood_happiness: float,
        mood_partiness: float,
        mood_relaxedness: float,
        mood_sadness: float,
        spectral_character_brightness: float,
        spectral_character_contrast_mean: float,
        spectral_character_valley_std: float,
    ) -> Track:
        # Convert lists to numpy arrays and serialize as binary data
        def serialize_array(arr):
            if arr is None:
                return None
            if isinstance(arr, list):
                arr = np.array(arr)
            return arr.tobytes()

        genre_embedding_bytes = serialize_array(genre_embedding)
        mfcc_covariance_bytes = serialize_array(mfcc_covariance)
        mfcc_mean_bytes = serialize_array(mfcc_mean)

        with self.Session() as session:
            # Check if track already exists
            existing_track = (
                session.query(Track).filter(Track.subsonic_id == subsonic_id).first()
            )

            if existing_track:
                return existing_track

            # Create a new track record
            track_record = Track(
                artist=artist,
                album=album,
                track=track,
                track_number=track_number,
                genre=genre,
                subsonic_id=subsonic_id,
                musicbrainz_artistid=musicbrainz_artistid,
                musicbrainz_albumid=musicbrainz_albumid,
                musicbrainz_trackid=musicbrainz_trackid,
                releasetype=releasetype,
                genre_embedding=genre_embedding_bytes,
                mfcc_covariance=mfcc_covariance_bytes,
                mfcc_mean=mfcc_mean_bytes,
                mfcc_temporal_variation=mfcc_temporal_variation,
                bpm=bpm,
                loudness=loudness,
                dynamic_complexity=dynamic_complexity,
                energy_curve_mean=energy_curve_mean,
                energy_curve_std=energy_curve_std,
                energy_curve_peak_count=energy_curve_peak_count,
                key_tonic=key_tonic,
                key_scale=key_scale,
                key_confidence=key_confidence,
                chord_unique_chords=chord_unique_chords,
                chord_change_rate=chord_change_rate,
                vocal_pitch_presence_ratio=vocal_pitch_presence_ratio,
                vocal_pitch_segment_count=vocal_pitch_segment_count,
                vocal_avg_pitch_duration=vocal_avg_pitch_duration,
                groove_beat_consistency=groove_beat_consistency,
                groove_danceability=groove_danceability,
                groove_dnc_bpm=groove_dnc_bpm,
                groove_syncopation=groove_syncopation,
                groove_tempo_stability=groove_tempo_stability,
                mood_aggressiveness=mood_aggressiveness,
                mood_happiness=mood_happiness,
                mood_partiness=mood_partiness,
                mood_relaxedness=mood_relaxedness,
                mood_sadness=mood_sadness,
                spectral_character_brightness=spectral_character_brightness,
                spectral_character_contrast_mean=spectral_character_contrast_mean,
                spectral_character_valley_std=spectral_character_valley_std,
            )

            session.add(track_record)
            session.commit()

            # Link genres using genre_list which looks like [{"label": "Heavy Metal", "score", 0.932}, ...]
            if genre_list:
                for genre_item in genre_list:
                    genre_label = genre_item["label"]
                    genre_score = genre_item["score"]

                    # Check if genre already exists
                    genre = (
                        session.query(Genre).filter(Genre.label == genre_label).first()
                    )
                    if not genre:
                        # Create new genre if it doesn't exist
                        genre = Genre(label=genre_label)
                        session.add(genre)
                        session.flush()  # Get the genre ID without committing

                    # Create track-genre relationship with score
                    track_genre = TrackGenre(
                        track_id=track_record.id, genre_id=genre.id, score=genre_score
                    )
                    session.add(track_genre)

                session.commit()

            # Merge the track back into the session
            track_record = session.merge(track_record)

            return track_record

    def get_track_by_subsonic_id(self, subsonic_id: str) -> Track | None:
        """Get a track based on subsonic id"""
        with self.Session() as session:
            return session.query(Track).filter(Track.subsonic_id == subsonic_id).first()
