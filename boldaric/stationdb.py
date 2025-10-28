# Copyright (c) 2025 Marcus Dillavou <line72@line72.net>
# Part of the Boldaric Project:
#  https://github.com/line72/boldaric
# Released under the AGPLv3 or later

# Web Server for the boldaric project
#
# This provides a RESTful API for creating stations, getting next
# tracks for a stations, rating songs, seeding songs, and so on.

import pickle
from typing import Optional
from datetime import datetime, timedelta
import os

from importlib import resources

from . import simulator
from .records.station_options import StationOptions

from alembic import command
from alembic.config import Config

from sqlalchemy import create_engine, and_, or_, func
from sqlalchemy.orm import sessionmaker

from .models import Base
from .models.user import User
from .models.station import Station
from .models.track_history import TrackHistory
from .models.embedding_history import EmbeddingHistory


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
        with resources.path("boldaric", "alembic.ini") as ini_path:
            alembic_cfg = Config(str(ini_path))

            # Override script_location to be absolute
            alembic_dir = os.path.join(os.path.dirname(ini_path), "alembic")
            alembic_cfg.set_main_option("script_location", alembic_dir)
            
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

    def get_user(self, username: str) -> dict | None:
        """Get a user by username."""
        with self.Session() as session:
            user = session.query(User).filter(User.username == username).first()
            if user:
                return {"id": user.id, "username": user.username}
        return None

    def get_all_users(self) -> list[tuple[int, str]]:
        with self.Session() as session:
            users = session.query(User).all()
            return [(user.id, user.username) for user in users]

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

    def get_stations_for_user(self, user_id: int) -> list:
        """Get all stations for a user."""
        with self.Session() as session:
            stations = session.query(Station).filter(Station.user_id == user_id).all()
            return [
                {
                    "id": station.id,
                    "name": station.name,
                    "replay_song_cooldown": station.replay_song_cooldown,
                    "replay_artist_downrank": station.replay_artist_downrank,
                    "ignore_live": station.ignore_live,
                }
                for station in stations
            ]

    def get_station_id(self, user_id: int, station_name: str) -> int | None:
        """Get a station ID by user ID and station name."""
        with self.Session() as session:
            station = session.query(Station).filter(
                Station.user_id == user_id,
                Station.name == station_name
            ).first()
            return station.id if station else None

    def get_station(self, user_id: int, station_id: str) -> dict | None:
        """Get a station by ID"""
        with self.Session() as session:
            station = session.query(Station).filter(
                Station.user_id == user_id,
                Station.id == station_id
            ).first()
            if station:
                return {
                    "id": station.id,
                    "name": station.name,
                    "replay_song_cooldown": station.replay_song_cooldown,
                    "replay_artist_downrank": station.replay_artist_downrank,
                    "ignore_live": station.ignore_live,
                }
        return None

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

    def get_station_embedding(self, station_id: int) -> list | None:
        """Get the current embedding for a station."""
        with self.Session() as session:
            station = session.query(Station).filter(Station.id == station_id).first()
            if station and station.current_embedding:
                return station.current_embedding
        return None

    def set_station_embedding(self, station_id: int, embedding: list):
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
        subsonic_id: str,
        artist: str,
        title: str,
        album: str,
        is_thumbs_downed: bool,
    ):
        """Add a track to the station's history. If it is recent, update the existing row"""
        with self.Session() as session:
            # Check if track already exists in history
            track_history = session.query(TrackHistory).filter(
                TrackHistory.station_id == station_id,
                TrackHistory.subsonic_id == subsonic_id
            ).first()

            if track_history:
                # Update existing record
                track_history.updated_at = datetime.now()
                # Only update thumbs_downed if it's being set to True
                if is_thumbs_downed:
                    track_history.is_thumbs_downed = is_thumbs_downed
                session.commit()
                return track_history.id
            else:
                # Create new record
                track_history = TrackHistory(
                    station_id=station_id,
                    subsonic_id=subsonic_id,
                    artist=artist,
                    title=title,
                    album=album,
                    is_thumbs_downed=is_thumbs_downed
                )
                session.add(track_history)
                session.commit()
                return track_history.id

    def get_track_history(
        self, station_id: int, limit: int = 20
    ) -> list[tuple[str, str, bool]]:
        """Get recent tracks played by a station."""
        with self.Session() as session:
            tracks = session.query(TrackHistory).filter(
                TrackHistory.station_id == station_id
            ).order_by(TrackHistory.updated_at.desc()).limit(limit).all()
            
            return [
                (track.artist, track.title, track.is_thumbs_downed)
                for track in tracks
            ]

    def get_thumbs_downed_history(self, station_id: int) -> list[tuple[str, str, bool]]:
        """Get all thumbs downed tracks by a station."""
        with self.Session() as session:
            tracks = session.query(TrackHistory).filter(
                and_(
                    TrackHistory.station_id == station_id,
                    TrackHistory.is_thumbs_downed == True
                )
            ).order_by(TrackHistory.updated_at).all()
            
            return [
                (track.artist, track.title, track.is_thumbs_downed)
                for track in tracks
            ]

    def add_embedding_history(
        self, station_id: int, track_history_id: int, embedding: list, rating: int
    ):
        """Add an embedding to the station's history."""
        with self.Session() as session:
            # Query for embeddings that match this track_history_id
            # AND were created in the previous 30 minutes OR is the
            # most recent embedding for this station
            thirty_minutes_ago = datetime.now() - timedelta(minutes=30)
            
            recent_embedding = session.query(EmbeddingHistory).filter(
                and_(
                    EmbeddingHistory.station_id == station_id,
                    EmbeddingHistory.track_history_id == track_history_id,
                    or_(
                        EmbeddingHistory.created_at >= thirty_minutes_ago,
                        EmbeddingHistory.id == session.query(
                            func.max(EmbeddingHistory.id)
                        ).filter(EmbeddingHistory.station_id == station_id)
                    )
                )
            ).order_by(EmbeddingHistory.created_at.desc()).first()

            # we have a recent embedding, if this was created in the last 30 minutes,
            # then just update it instead of creating a second one. Likely, the client
            # did something dumb, and played a song twice in a row or something...
            if recent_embedding:
                # Update it
                recent_embedding.rating = rating
            else:
                # Create new embedding
                embedding_history = EmbeddingHistory(
                    station_id=station_id,
                    track_history_id=track_history_id,
                    embedding=embedding,
                    rating=rating
                )
                session.add(embedding_history)
            
            session.commit()

    def get_embedding_history(self, station_id: int) -> list[tuple[list, int]]:
        """Get embedding history for a station."""
        with self.Session() as session:
            embeddings = session.query(EmbeddingHistory).filter(
                EmbeddingHistory.station_id == station_id
            ).order_by(EmbeddingHistory.created_at).all()
            
            return [
                (embedding.embedding, embedding.rating)
                for embedding in embeddings
            ]

    def load_station_history(self, station_id: int) -> tuple[list, list, list]:
        """Load embedding history, track history, and thumbs downed history for a station."""
        embeddings = self.get_embedding_history(station_id)
        tracks = self.get_track_history(station_id)

        # Build history from embeddings
        history = simulator.make_history()
        for embedding, rating in embeddings:
            history = simulator.add_history(history, embedding, rating)

        # Build thumbs downed from track history
        thumbs_downed = []
        with self.Session() as session:
            thumbs_downed_tracks = session.query(TrackHistory).filter(
                and_(
                    TrackHistory.station_id == station_id,
                    TrackHistory.is_thumbs_downed == True
                )
            ).order_by(TrackHistory.created_at).all()
            
            thumbs_downed = [
                {"metadata": {"artist": track.artist, "title": track.title, "album": track.album}}
                for track in thumbs_downed_tracks
            ]

        return history, tracks, thumbs_downed
