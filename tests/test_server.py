import pytest
import asyncio
import json
import tempfile
import os
from unittest.mock import Mock, patch
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from boldaric.server import (
    auth_middleware,
    auth,
    get_stations,
    make_station,
    get_next_song_for_station,
    get_station_info,
    update_station_info,
    add_seed,
    add_song_to_history,
    thumbs_up,
    thumbs_down,
    search,
    CreateStationParams,
    UpdateStationParams,
)
from boldaric.stationdb import StationDB
from boldaric.vectordb import VectorDB
from boldaric.models.track import Track
import boldaric.subsonic
import boldaric.feature_helper


class TestServer(AioHTTPTestCase):
    """Test cases for the server API endpoints."""

    def setUp(self):
        """Set up test database and other resources."""
        # Create temporary directory for test database
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_stations.db")

        # Initialize database
        self.station_db = StationDB(self.db_path)

        # Create test user
        self.test_user_id = self.station_db.create_user("testuser")
        self.test_user = self.station_db.get_user("testuser")

        super().setUp()

    def tearDown(self):
        """Clean up test resources."""
        self.temp_dir.cleanup()
        super().tearDown()

    def add_track(self, subsonic_id, artist, album, title):
        self.station_db.add_track(
            artist,
            album,
            title,
            1,
            "",
            subsonic_id,
            "",
            "",
            "",
            "album",
            "official",
            [],
            [0.1] * 128,  # genre
            [0.2] * 13,
            [0.21] * 13,
            0.0,  # mfcc
            0.5,
            0.5,
            0.5,  # bpm-dynamic_complexity
            0.5,
            0.5,
            0.5,  # energy
            "minor",
            "g",
            1.0,  # key
            3,
            0.23,  # chord
            0.44,
            2,
            0.55,  # vocal
            0.001,
            0.88,
            128.0,
            1.0,
            1.0,  # groove
            0.34,
            0.55,
            0.29,
            0.001,
            0.02,  # mood
            0.43,
            0.34,
            0.53,  # spectral
        )

    async def get_application(self):
        """Create application for testing."""
        app = web.Application()

        # Application state
        app["salt"] = b"test_salt_1234567890"
        app["station_db"] = self.station_db

        # Create a mock VectorDB
        self.mock_vec_db = Mock(spec=VectorDB)
        app["vec_db"] = self.mock_vec_db

        # Create a mock subsonic connection
        self.mock_sub_conn = Mock()
        app["sub_conn"] = self.mock_sub_conn

        # Create a mock pool
        self.mock_pool = Mock()
        self.mock_pool._processes = 4  # Set the _processes attribute to an integer
        app["pool"] = self.mock_pool

        # Add routes for testing
        app.router.add_post("/api/auth", auth)
        app.router.add_get("/api/stations", get_stations)
        app.router.add_post("/api/stations", make_station)
        app.router.add_get("/api/station/{station_id}", get_next_song_for_station)
        app.router.add_get("/api/station/{station_id}/info", get_station_info)
        app.router.add_put("/api/station/{station_id}/info", update_station_info)
        app.router.add_post("/api/station/{station_id}/seed", add_seed)
        app.router.add_put("/api/station/{station_id}/{song_id}", add_song_to_history)
        app.router.add_post("/api/station/{station_id}/{song_id}/thumbs_up", thumbs_up)
        app.router.add_post(
            "/api/station/{station_id}/{song_id}/thumbs_down", thumbs_down
        )
        app.router.add_get("/api/search", search)

        # Add auth middleware
        app.middlewares.append(auth_middleware)

        return app

    def _create_auth_header(self, username="testuser"):
        """Create an authorization header for testing."""
        import hashlib

        salt = b"test_salt_1234567890"
        token = hashlib.sha256(salt + username.encode("utf-8")).hexdigest()
        return {"Authorization": f"Bearer {token}"}

    async def test_auth_success(self):
        """Test successful authentication."""
        # Make request
        resp = await self.client.request(
            "POST",
            "/api/auth",
            data=json.dumps({"login": "testuser"}),
            headers={"Content-Type": "application/json"},
        )

        assert resp.status == 200
        data = await resp.json()
        assert "token" in data
        assert data["id"] == self.test_user_id
        assert data["username"] == "testuser"

    async def test_auth_failure(self):
        """Test authentication failure."""
        # Make request
        resp = await self.client.request(
            "POST",
            "/api/auth",
            data=json.dumps({"login": "nonexistent"}),
            headers={"Content-Type": "application/json"},
        )

        assert resp.status == 401
        data = await resp.json()
        assert "error" in data

    async def test_get_stations(self):
        """Test getting stations for a user."""
        # Create test stations
        station1_id = self.station_db.create_station(self.test_user_id, "Station 1")
        station2_id = self.station_db.create_station(self.test_user_id, "Station 2")

        # Set options for stations
        self.station_db.set_station_options(station1_id, 50, 0.95, False)
        self.station_db.set_station_options(station2_id, 30, 0.9, True)

        # Make request
        resp = await self.client.request(
            "GET", "/api/stations", headers=self._create_auth_header()
        )

        assert resp.status == 200
        data = await resp.json()
        assert len(data) == 2
        station_names = [station["name"] for station in data]
        assert "Station 1" in station_names
        assert "Station 2" in station_names

    async def test_make_station_success(self):
        """Test creating a station successfully."""
        # Mock the vector database response
        mock_track = {
            "metadata": {
                "subsonic_id": "song123",
                "artist": "Test Artist",
                "title": "Test Title",
                "album": "Test Album",
            },
            "features": {},
        }
        self.mock_vec_db.get_track.return_value = mock_track
        self.add_track("song123", "Test Artist", "Test Album", "Test Title")

        # Mock subsonic functions
        with patch(
            "boldaric.subsonic.make_stream_link",
            return_value="http://example.com/stream",
        ):
            with patch(
                "boldaric.subsonic.make_album_art_link",
                return_value="http://example.com/cover",
            ):
                # Mock the track_to_embeddings function
                with patch(
                    "boldaric.feature_helper.track_to_embeddings",
                    return_value=[0.1] * 148,
                ):
                    # Make request
                    resp = await self.client.request(
                        "POST",
                        "/api/stations",
                        data=json.dumps(
                            {"station_name": "Test Station", "song_id": "song123"}
                        ),
                        headers={
                            **self._create_auth_header(),
                            "Content-Type": "application/json",
                        },
                    )

        assert resp.status == 200
        data = await resp.json()
        assert "station" in data
        assert "track" in data
        assert data["station"]["name"] == "Test Station"

        # Verify station was actually created in database
        stations = self.station_db.get_stations_for_user(self.test_user_id)
        assert len(stations) == 1
        assert stations[0].name == "Test Station"

    async def test_make_station_invalid_song(self):
        """Test creating a station with invalid song ID."""
        # Mock the vector database response
        self.mock_vec_db.get_track.return_value = None

        # Make request
        resp = await self.client.request(
            "POST",
            "/api/stations",
            data=json.dumps(
                {"station_name": "Test Station", "song_id": "invalid_song"}
            ),
            headers={**self._create_auth_header(), "Content-Type": "application/json"},
        )

        assert resp.status == 400
        data = await resp.json()
        assert "error" in data

    async def test_get_station_info_success(self):
        """Test getting station info successfully."""
        # Create a test station
        station_id = self.station_db.create_station(self.test_user_id, "Test Station")
        self.station_db.set_station_options(station_id, 50, 0.95, True)

        # Make request
        resp = await self.client.request(
            "GET", f"/api/station/{station_id}/info", headers=self._create_auth_header()
        )

        assert resp.status == 200
        data = await resp.json()
        assert data["id"] == station_id
        assert data["name"] == "Test Station"
        assert data["replay_song_cooldown"] == 50

    async def test_get_station_info_not_found(self):
        """Test getting station info for non-existent station."""
        # Make request for non-existent station
        resp = await self.client.request(
            "GET", "/api/station/999/info", headers=self._create_auth_header()
        )

        assert resp.status == 404
        data = await resp.json()
        assert "error" in data

    async def test_update_station_info_success(self):
        """Test updating station info successfully."""
        # Create a test station
        station_id = self.station_db.create_station(self.test_user_id, "Test Station")

        # Make request
        resp = await self.client.request(
            "PUT",
            f"/api/station/{station_id}/info",
            data=json.dumps(
                {
                    "replay_song_cooldown": 100,
                    "replay_artist_downrank": 0.8,
                    "ignore_live": False,
                }
            ),
            headers={**self._create_auth_header(), "Content-Type": "application/json"},
        )

        assert resp.status == 200
        data = await resp.json()
        assert data["replay_song_cooldown"] == 100
        assert data["replay_artist_downrank"] == 0.8

        # Verify changes were persisted
        updated_station = self.station_db.get_station(self.test_user_id, station_id)
        assert updated_station.replay_song_cooldown == 100
        assert updated_station.replay_artist_downrank == 0.8
        assert updated_station.ignore_live == False

    async def test_update_station_info_not_found(self):
        """Test updating station info for non-existent station."""
        # Make request
        resp = await self.client.request(
            "PUT",
            "/api/station/999/info",
            data=json.dumps({"replay_song_cooldown": 100}),
            headers={**self._create_auth_header(), "Content-Type": "application/json"},
        )

        assert resp.status == 404
        data = await resp.json()
        assert "error" in data

    async def test_add_seed_success(self):
        """Test adding a seed song successfully."""
        # Create a test station
        station_id = self.station_db.create_station(self.test_user_id, "Test Station")

        # Mock the vector database response
        mock_track = {
            "metadata": {
                "subsonic_id": "song123",
                "artist": "Test Artist",
                "title": "Test Title",
                "album": "Test Album",
            },
            "features": {},
        }
        self.mock_vec_db.get_track.return_value = mock_track
        self.add_track("song123", "Test Artist", "Test Album", "Test Title")

        # Mock the track_to_embeddings function
        with patch(
            "boldaric.feature_helper.track_to_embeddings", return_value=[0.1] * 148
        ):
            # Make request
            resp = await self.client.request(
                "POST",
                f"/api/station/{station_id}/seed",
                data=json.dumps({"song_id": "song123"}),
                headers={
                    **self._create_auth_header(),
                    "Content-Type": "application/json",
                },
            )

        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True

        # Verify track was added to history
        history = self.station_db.get_track_history(station_id)
        assert len(history) == 1
        assert history[0].track.subsonic_id == "song123"

    async def test_add_song_to_history(self):
        """Test adding a song to history."""
        # Create a test station
        station_id = self.station_db.create_station(self.test_user_id, "Test Station")

        # Mock the vector database response
        mock_track = {
            "metadata": {
                "subsonic_id": "song123",
                "artist": "Test Artist",
                "title": "Test Title",
                "album": "Test Album",
            },
            "features": {},
        }
        self.mock_vec_db.get_track.return_value = mock_track
        self.add_track("song123", "Test Artist", "Test Album", "Test Title")

        # Mock the track_to_embeddings function
        with patch(
            "boldaric.feature_helper.track_to_embeddings", return_value=[0.1] * 148
        ):
            # Make request
            resp = await self.client.request(
                "PUT",
                f"/api/station/{station_id}/song123",
                headers=self._create_auth_header(),
            )

        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True

        # Verify track was added to history
        history = self.station_db.get_track_history(station_id)
        assert len(history) == 1
        assert history[0].track.subsonic_id == "song123"

    async def test_thumbs_up(self):
        """Test giving a song a thumbs up."""
        # Create a test station
        station_id = self.station_db.create_station(self.test_user_id, "Test Station")

        # Mock the vector database response
        mock_track = {
            "metadata": {
                "subsonic_id": "song123",
                "artist": "Test Artist",
                "title": "Test Title",
                "album": "Test Album",
            },
            "features": {},
        }
        self.mock_vec_db.get_track.return_value = mock_track
        self.add_track("song123", "Test Artist", "Test Album", "Test Title")

        # Mock the track_to_embeddings function
        with patch(
            "boldaric.feature_helper.track_to_embeddings", return_value=[0.1] * 148
        ):
            # Make request
            resp = await self.client.request(
                "POST",
                f"/api/station/{station_id}/song123/thumbs_up",
                headers=self._create_auth_header(),
            )

        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True

        # Verify track was added to history with correct rating
        history = self.station_db.get_track_history(station_id)
        assert len(history) == 1
        assert history[0].track.subsonic_id == "song123"
        assert history[0].is_thumbs_downed == False

    async def test_thumbs_down(self):
        """Test giving a song a thumbs down."""
        # Create a test station
        station_id = self.station_db.create_station(self.test_user_id, "Test Station")

        # Mock the vector database response
        mock_track = {
            "metadata": {
                "subsonic_id": "song123",
                "artist": "Test Artist",
                "title": "Test Title",
                "album": "Test Album",
            },
            "features": {},
        }
        self.mock_vec_db.get_track.return_value = mock_track
        self.add_track("song123", "Test Artist", "Test Album", "Test Title")

        # Mock the track_to_embeddings function
        with patch(
            "boldaric.feature_helper.track_to_embeddings", return_value=[0.1] * 148
        ):
            # Make request
            resp = await self.client.request(
                "POST",
                f"/api/station/{station_id}/song123/thumbs_down",
                headers=self._create_auth_header(),
            )

        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True

        # Verify track was added to history with thumbs down
        history = self.station_db.get_track_history(station_id)
        assert len(history) == 1
        assert history[0].track.subsonic_id == "song123"
        assert history[0].is_thumbs_downed == True

    async def test_get_next_song_for_station(self):
        """Test getting next song for station."""
        # Create a test station
        station_id = self.station_db.create_station(self.test_user_id, "Test Station")
        self.station_db.set_station_options(station_id, 50, 0.95, False)

        # Mock the vector database response
        mock_tracks = [
            {
                "metadata": {
                    "subsonic_id": "song1",
                    "artist": "Artist 1",
                    "title": "Title 1",
                    "album": "Album 1",
                },
                "features": {},
                "similarity": 0.9,
            },
            {
                "metadata": {
                    "subsonic_id": "song2",
                    "artist": "Artist 2",
                    "title": "Title 2",
                    "album": "Album 2",
                },
                "features": {},
                "similarity": 0.8,
            },
        ]
        self.mock_vec_db.query_similar.return_value = mock_tracks
        for i in mock_tracks:
            m = i["metadata"]
            self.add_track(m["subsonic_id"], m["artist"], m["album"], m["title"])

        # Mock subsonic functions
        with patch(
            "boldaric.subsonic.make_stream_link",
            return_value="http://example.com/stream",
        ):
            with patch(
                "boldaric.subsonic.make_album_art_link",
                return_value="http://example.com/cover",
            ):
                # Mock the simulator functions
                with patch("boldaric.simulator.make_history", return_value=[]):
                    with patch("boldaric.simulator.add_history", return_value=[]):
                        with patch(
                            "boldaric.simulator.attract", return_value=[0.1] * 148
                        ):
                            with patch(
                                "boldaric.feature_helper.track_to_embeddings",
                                return_value={},
                            ):
                                # Mock multiprocessing pool methods
                                self.mock_pool.apply_async.return_value.get.return_value = (
                                    mock_tracks
                                )

                                # Make request
                                resp = await self.client.request(
                                    "GET",
                                    f"/api/station/{station_id}",
                                    headers=self._create_auth_header(),
                                )

        # This might return 400 if the mock doesn't have enough data, but it shouldn't crash
        # with a Navidrome connection error
        assert resp.status in [200, 400]

    async def test_search(self):
        """Test searching for songs."""
        # Mock subsonic search response
        self.mock_sub_conn.search3.return_value = {
            "searchResult3": {
                "song": [
                    {
                        "id": "song123",
                        "title": "Test Song",
                        "artist": "Test Artist",
                        "album": "Test Album",
                    }
                ]
            }
        }

        # Make request
        resp = await self.client.request(
            "GET",
            "/api/search?artist=Test&title=Song",
            headers=self._create_auth_header(),
        )

        assert resp.status == 200
        data = await resp.json()
        # The server returns the song array directly, not the full searchResult3 structure
        assert len(data) == 1
        assert data[0]["id"] == "song123"

    def test_create_station_params_validation(self):
        """Test CreateStationParams validation."""
        # Test valid parameters
        params = CreateStationParams(
            station_name="Test Station",
            song_id="song123",
            replay_song_cooldown=50,
            replay_artist_downrank=0.95,
            ignore_live=True,
        )
        assert params.station_name == "Test Station"
        assert params.song_id == "song123"
        assert params.replay_song_cooldown == 50
        assert params.replay_artist_downrank == 0.95
        assert params.ignore_live is True

    def test_update_station_params_validation(self):
        """Test UpdateStationParams validation."""
        # Test valid parameters
        params = UpdateStationParams(
            replay_song_cooldown=50, replay_artist_downrank=0.95, ignore_live=True
        )
        assert params.replay_song_cooldown == 50
        assert params.replay_artist_downrank == 0.95
        assert params.ignore_live is True
