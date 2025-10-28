# Copyright (c) 2025 Marcus Dillavou <line72@line72.net>
# Part of the Boldaric Project:
#  https://github.com/line72/boldaric
# Released under the AGPLv3 or later

# Web Server for the boldaric project
#
# This provides a RESTful API for creating stations, getting next
# tracks for a stations, rating songs, seeding songs, and so on.

import sqlite3
import pickle
from typing import Optional
from datetime import datetime
import numpy as np

from importlib import resources

from . import simulator
from .records.station_options import StationOptions
from .records.track import Track

from alembic import command
from alembic.config import Config
import os


class StationDB:
    """
    A simple SQLite-based persistence layer for user stations and playback history.
    """

    def __init__(self, db_path: str = "stations.db"):
        self.db_path = db_path
        self._run_migrations()

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

    def _connect(self) -> sqlite3.Connection:
        """Create a new database connection."""
        connection = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=10.0,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL;")

        return connection

    # ----------------------
    # User Management
    # ----------------------

    def create_user(self, username: str) -> int:
        """Create a new user and return their ID."""
        with self._connect() as conn:
            cur = conn.execute("INSERT INTO users (username) VALUES (?)", (username,))
            return cur.lastrowid

    def get_user(self, username: str) -> dict | None:
        """Get a user by username."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, username FROM users WHERE username = ?", (username,)
            ).fetchone()
            return {"id": row[0], "username": row[1]} if row else None

    def get_all_users(self) -> list[tuple[int, str]]:
        with self._connect() as conn:
            return [
                (row[0], row[1])
                for row in conn.execute("SELECT id, username FROM users").fetchall()
            ]

    # ----------------------
    # Station Management
    # ----------------------

    def create_station(self, user_id: int, station_name: str) -> int:
        """Create a new station for a user."""
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO stations (user_id, name) VALUES (?, ?)",
                (user_id, station_name),
            )
            return cur.lastrowid

    def get_stations_for_user(self, user_id: int) -> list:
        """Get all stations for a user."""
        with self._connect() as conn:
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "replay_song_cooldown": row[2],
                    "replay_artist_downrank": row[3],
                    "ignore_live": row[4],
                }
                for row in conn.execute(
                    "SELECT id, name, replay_song_cooldown, replay_artist_downrank, ignore_live FROM stations WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
            ]

    def get_station_id(self, user_id: int, station_name: str) -> int | None:
        """Get a station ID by user ID and station name."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM stations WHERE user_id = ? AND name = ?",
                (user_id, station_name),
            ).fetchone()
            return row[0] if row else None

    def get_station(self, user_id: int, station_id: str) -> dict | None:
        """Get a station by ID"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, replay_song_cooldown, replay_artist_downrank, ignore_live FROM stations WHERE user_id = ? AND id = ?",
                (user_id, station_id),
            ).fetchone()
            return (
                {
                    "id": row[0],
                    "name": row[1],
                    "replay_song_cooldown": row[2],
                    "replay_artist_downrank": row[3],
                    "ignore_live": row[4],
                }
                if row
                else None
            )

    def get_station_options(self, station_id: int) -> StationOptions:
        """Get the options for a station"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT replay_song_cooldown, replay_artist_downrank, ignore_live FROM stations WHERE id = ?",
                (station_id,),
            ).fetchone()

            return StationOptions(
                replay_song_cooldown=row[0],
                replay_artist_downrank=row[1],
                ignore_live=row[2],
            )

    def set_station_options(
        self,
        station_id: int,
        replay_song_cooldown: int,
        replay_artist_downrank: float,
        ignore_live: bool,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE stations SET replay_song_cooldown = ?, replay_artist_downrank = ?, ignore_live = ? WHERE id = ?",
                (replay_song_cooldown, replay_artist_downrank, ignore_live, station_id),
            )

    def get_station_embedding(self, station_id: int) -> list | None:
        """Get the current embedding for a station."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT current_embedding FROM stations WHERE id = ?", (station_id,)
            ).fetchone()
            if row and row[0]:
                return pickle.loads(row[0])
        return None

    def set_station_embedding(self, station_id: int, embedding: list):
        """Set the current embedding for a station."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE stations SET current_embedding = ? WHERE id = ?",
                (pickle.dumps(embedding), station_id),
            )

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
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM track_history WHERE station_id = ? AND subsonic_id = ?",
                (station_id, subsonic_id),
            ).fetchone()

            if row:
                # just update it, if we have thumbsed it down
                #  then set that. We only go from !thumbs_downed -> thumbs_downed,
                #  not the other way (you can't unset this magically)
                if is_thumbs_downed:
                    conn.execute(
                        "UPDATE track_history SET updated_at = CURRENT_TIMESTAMP, is_thumbs_downed = ? WHERE id = ?",
                        (is_thumbs_downed, row[0]),
                    )
                    return row[0]
                else:
                    conn.execute(
                        "UPDATE track_history SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (row[0],),
                    )
                    return row[0]
            else:
                cursor = conn.execute(
                    "INSERT INTO track_history (station_id, subsonic_id, artist, title, album, is_thumbs_downed) VALUES (?, ?, ?, ?, ?, ?)",
                    (station_id, subsonic_id, artist, title, album, is_thumbs_downed),
                )
                return cursor.lastrowid

    def get_track_history(
        self, station_id: int, limit: int = 20
    ) -> list[tuple[str, str, bool]]:
        """Get recent tracks played by a station."""
        with self._connect() as conn:
            return [
                (row[0], row[1], row[2])  # (artist, title, thumbs_downed)
                for row in conn.execute(
                    "SELECT artist, title, is_thumbs_downed FROM track_history WHERE station_id = ? ORDER BY updated_at DESC LIMIT ?",
                    (station_id, limit),
                ).fetchall()
            ]

    def get_thumbs_downed_history(self, station_id: int) -> list[tuple[str, str, bool]]:
        """Get all thumbs downed tracks by a station."""
        with self._connect() as conn:
            return [
                (row[0], row[1], row[2])  # (artist, title, thumbs_downed)
                for row in conn.execute(
                    "SELECT artist, title, is_thumbs_downed FROM track_history WHERE station_id = ? AND is_thumbs_downed=true ORDER BY updated_at",
                    (station_id,),
                ).fetchall()
            ]

    def add_embedding_history(
        self, station_id: int, track_history_id: int, embedding: list, rating: int
    ):
        """Add an embedding to the station's history."""
        with self._connect() as conn:
            # Query for embeddings that match this track_history_id
            #  AND were created in the previous 30 minutes OR is the
            #  most recent embedding for this station
            row = conn.execute(
                """
                SELECT id, created_at 
                FROM embedding_history 
                WHERE station_id = ? 
                  AND track_history_id = ? 
                  AND (
                    created_at >= datetime('now', '-30 minutes')
                    OR id = (
                      SELECT id 
                      FROM embedding_history 
                      WHERE station_id = embedding_history.station_id 
                      ORDER BY created_at DESC 
                      LIMIT 1
                    )
                  )
                ORDER BY created_at DESC 
                LIMIT 1
            """,
                (station_id, track_history_id),
            ).fetchone()

            # we have a recent embedding, if this was created in the last 30 minutes,
            #  then just update it instead of creating a second one. Likely, the client
            #  did something dumb, and played a song twice in a row or something...
            if row:
                # Update it
                conn.execute(
                    "UPDATE embedding_history SET rating = ? WHERE id = ?",
                    (rating, row[0]),
                )
            else:
                conn.execute(
                    "INSERT INTO embedding_history (station_id, track_history_id, embedding, rating) VALUES (?, ?, ?, ?)",
                    (station_id, track_history_id, pickle.dumps(embedding), rating),
                )

    def get_embedding_history(self, station_id: int) -> list[tuple[list, int]]:
        """Get embedding history for a station."""
        with self._connect() as conn:
            return [
                (pickle.loads(row[0]), row[1])  # (embedding, rating)
                for row in conn.execute(
                    "SELECT embedding, rating FROM embedding_history WHERE station_id = ? ORDER BY created_at",
                    (station_id,),
                ).fetchall()
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
        with self._connect() as conn:
            thumbs_downed = [
                {"metadata": {"artist": row[0], "title": row[1], "album": row[2]}}
                for row in conn.execute(
                    "SELECT artist, title, album FROM track_history WHERE station_id = ? AND is_thumbs_downed = 1 ORDER BY created_at",
                    (station_id,),
                ).fetchall()
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
    ) -> int:
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
        
        # Get current timestamp
        now = datetime.now()
        
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO tracks (artist, album, track, track_number, genre, subsonic_id, musicbrainz_artistid, musicbrainz_albumid, musicbrainz_trackid, releasetype, genre_embedding, mfcc_covariance, mfcc_mean, mfcc_temporal_variation, bpm, loudness, dynamic_complexity, energy_curve_mean, energy_curve_std, energy_curve_peak_count, key_tonic, key_scale, key_confidence, chord_unique_chords, chord_change_rate, vocal_pitch_presence_ratio, vocal_pitch_segment_count, vocal_avg_pitch_duration, groove_beat_consistency, groove_danceability, groove_dnc_bpm, groove_syncopation, groove_tempo_stability, mood_aggressiveness, mood_happiness, mood_partiness, mood_relaxedness, mood_sadness, spectral_character_brightness, spectral_character_contrast_mean, spectral_character_valley_std, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    artist,
                    album,
                    track,
                    track_number,
                    genre,
                    subsonic_id,
                    musicbrainz_artistid,
                    musicbrainz_albumid,
                    musicbrainz_trackid,
                    releasetype,
                    genre_embedding_bytes,
                    mfcc_covariance_bytes,
                    mfcc_mean_bytes,
                    mfcc_temporal_variation,
                    bpm,
                    loudness,
                    dynamic_complexity,
                    energy_curve_mean,
                    energy_curve_std,
                    energy_curve_peak_count,
                    key_tonic,
                    key_scale,
                    key_confidence,
                    chord_unique_chords,
                    chord_change_rate,
                    vocal_pitch_presence_ratio,
                    vocal_pitch_segment_count,
                    vocal_avg_pitch_duration,
                    groove_beat_consistency,
                    groove_danceability,
                    groove_dnc_bpm,
                    groove_syncopation,
                    groove_tempo_stability,
                    mood_aggressiveness,
                    mood_happiness,
                    mood_partiness,
                    mood_relaxedness,
                    mood_sadness,
                    spectral_character_brightness,
                    spectral_character_contrast_mean,
                    spectral_character_valley_std,
                    now,  # created_at
                    now,  # updated_at
                ),
            )
            return cur.lastrowid

    def get_track_by_subsonic_id(self, subsonic_id: str) -> Track | None:
        """Get a track based on subsonic id"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tracks WHERE subsonic_id = ?", (subsonic_id,)
            ).fetchone()
            if row:
                # Deserialize binary data back to numpy arrays
                def deserialize_array(binary_data, shape=None):
                    """Deserialize binary data back to numpy array"""
                    if binary_data is None:
                        return None
                    arr = np.frombuffer(binary_data, dtype=np.float64)
                    if shape:
                        arr = arr.reshape(shape)
                    return arr

                # Deserialize the binary fields
                genre_embedding_array = deserialize_array(row["genre_embedding"])
                mfcc_mean_array = deserialize_array(row["mfcc_mean"])
                mfcc_covariance_array = deserialize_array(row["mfcc_covariance"], (13, 13))

                track = Track(
                    tid=row["id"],
                    artist=row["artist"],
                    album=row["album"],
                    track=row["track"],
                    track_number=row["track_number"],
                    genre=row["genre"],
                    subsonic_id=row["subsonic_id"],
                    musicbrainz_artistid=row["musicbrainz_artistid"],
                    musicbrainz_albumid=row["musicbrainz_albumid"],
                    musicbrainz_trackid=row["musicbrainz_trackid"],
                    releasetype=row["releasetype"],
                    genre_embedding=genre_embedding_array,
                    mfcc_covariance=mfcc_covariance_array,
                    mfcc_mean=mfcc_mean_array,
                    mfcc_temporal_variation=row["mfcc_temporal_variation"],
                    bpm=row["bpm"],
                    loudness=row["loudness"],
                    dynamic_complexity=row["dynamic_complexity"],
                    energy_curve_mean=row["energy_curve_mean"],
                    energy_curve_std=row["energy_curve_std"],
                    energy_curve_peak_count=row["energy_curve_peak_count"],
                    key_tonic=row["key_tonic"],
                    key_scale=row["key_scale"],
                    key_confidence=row["key_confidence"],
                    chord_unique_chords=row["chord_unique_chords"],
                    chord_change_rate=row["chord_change_rate"],
                    vocal_pitch_presence_ratio=row["vocal_pitch_presence_ratio"],
                    vocal_pitch_segment_count=row["vocal_pitch_segment_count"],
                    vocal_avg_pitch_duration=row["vocal_avg_pitch_duration"],
                    groove_beat_consistency=row["groove_beat_consistency"],
                    groove_danceability=row["groove_danceability"],
                    groove_dnc_bpm=row["groove_dnc_bpm"],
                    groove_syncopation=row["groove_syncopation"],
                    groove_tempo_stability=row["groove_tempo_stability"],
                    mood_aggressiveness=row["mood_aggressiveness"],
                    mood_happiness=row["mood_happiness"],
                    mood_partiness=row["mood_partiness"],
                    mood_relaxedness=row["mood_relaxedness"],
                    mood_sadness=row["mood_sadness"],
                    spectral_character_brightness=row["spectral_character_brightness"],
                    spectral_character_contrast_mean=row["spectral_character_contrast_mean"],
                    spectral_character_valley_std=row["spectral_character_valley_std"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                
                return track
            else:
                return None
