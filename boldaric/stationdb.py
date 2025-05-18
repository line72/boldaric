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

from . import simulator

class StationDB:
    """
    A simple SQLite-based persistence layer for user stations and playback history.
    """

    def __init__(self, db_path: str = "stations.db"):
        self.db_path = db_path
        self._initialize_db()

    def _connect(self) -> sqlite3.Connection:
        """Create a new database connection."""
        return sqlite3.connect(self.db_path)

    def _initialize_db(self):
        """Create tables if they don't exist."""
        with self._connect() as conn:
            # Users table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL
                )
            """
            )

            # Stations table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    current_embedding BLOB,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, name)
                )
            """
            )

            # Track history table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS track_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    station_id INTEGER NOT NULL,
                    subsonic_id TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    title TEXT NOT NULL,
                    album TEXT,
                    is_thumbs_downed BOOLEAN NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
                )
            """
            )

            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_station_subsonic
                    ON track_history(station_id, subsonic_id);
            """
            )

            # Embedding history table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS embedding_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    station_id INTEGER NOT NULL,
                    track_history_id INTEGER NOT NULL,
                    embedding BLOB NOT NULL,
                    rating INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
                    FOREIGN KEY(track_history_id) REFERENCES track_history(id) ON DELETE CASCADE
                )
            """
            )

            conn.commit()

    # ----------------------
    # User Management
    # ----------------------

    def create_user(self, username: str) -> int:
        """Create a new user and return their ID."""
        with self._connect() as conn:
            cur = conn.execute("INSERT INTO users (username) VALUES (?)", (username,))
            return cur.lastrowid

    def get_user(self, username: str) -> tuple[int, str] | None:
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
                {"id": row[0], "name": row[1]}
                for row in conn.execute(
                    "SELECT id, name FROM stations WHERE user_id = ?", (user_id,)
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

    def get_station(self, user_id: int, station_id: str) -> dict:
        """Get a station by ID"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name FROM stations WHERE user_id = ? AND id = ?",
                (user_id, station_id),
            ).fetchone()
            return {"id": row[0], "name": row[1]} if row else None

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
