import os
import tempfile
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from boldaric.stationdb import StationDB
from boldaric.records.station_options import StationOptions
from boldaric.models.track import Track


@pytest.fixture(scope="function")
def station_db():
    """Create a temporary StationDB instance for testing."""
    # Create a temporary directory for the database
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_stations.db")
        db = StationDB(db_path)
        yield db

def create_track(station_db, artist, album, title, subsonic_id):
    station_db.add_track(artist, album, title, 1, '',
                         subsonic_id, '', '', '', 'album',
                         [], [0.1]*128, #genre
                         [0.2]*13, [0.21]*13, 0.0, #mfcc
                         0.5, 0.5, 0.5, #bpm-dynamic_complexity
                         0.5, 0.5, 0.5, #energy
                         'minor', 'g', 1.0, #key
                         3, 0.23, #chord
                         0.44, 2, 0.55, #vocal
                         0.001, 0.88, 128.0, 1.0, 1.0, # groove
                         0.34, 0.55, 0.29, 0.001, 0.02, # mood
                         0.43, 0.34, 0.53 #spectral
                         )
    return station_db.get_track_by_subsonic_id(subsonic_id)

def test_create_user(station_db):
    """Test creating a user."""
    user_id = station_db.create_user("testuser")
    assert user_id is not None
    assert isinstance(user_id, int)
    assert user_id > 0


def test_get_user(station_db):
    """Test getting a user by username."""
    # Create a user first
    station_db.create_user("testuser")
    
    # Get the user
    user = station_db.get_user("testuser")
    assert user is not None
    assert user.username == "testuser"


def test_get_user_not_found(station_db):
    """Test getting a non-existent user."""
    user = station_db.get_user("nonexistent")
    assert user is None


def test_get_all_users(station_db):
    """Test getting all users."""
    # Create some users
    station_db.create_user("user1")
    station_db.create_user("user2")
    station_db.create_user("user3")
    
    users = station_db.get_all_users()
    assert len(users) == 3
    usernames = [user.username for user in users]
    assert "user1" in usernames
    assert "user2" in usernames
    assert "user3" in usernames


def test_create_station(station_db):
    """Test creating a station for a user."""
    # Create a user first
    user_id = station_db.create_user("testuser")
    
    # Create a station
    station_id = station_db.create_station(user_id, "Test Station")
    assert station_id is not None
    assert isinstance(station_id, int)
    assert station_id > 0


def test_get_stations_for_user(station_db):
    """Test getting all stations for a user."""
    # Create a user
    user_id = station_db.create_user("testuser")
    
    # Create some stations
    station_db.create_station(user_id, "Station 1")
    station_db.create_station(user_id, "Station 2")
    
    # Get stations for user
    stations = station_db.get_stations_for_user(user_id)
    assert len(stations) == 2
    station_names = [station.name for station in stations]
    assert "Station 1" in station_names
    assert "Station 2" in station_names


def test_get_station_id(station_db):
    """Test getting a station ID by user ID and station name."""
    # Create a user
    user_id = station_db.create_user("testuser")
    
    # Create a station
    station_db.create_station(user_id, "Test Station")
    
    # Get station ID
    station_id = station_db.get_station_id(user_id, "Test Station")
    assert station_id is not None
    assert isinstance(station_id, int)
    assert station_id > 0


def test_get_station_id_not_found(station_db):
    """Test getting a non-existent station ID."""
    # Create a user
    user_id = station_db.create_user("testuser")
    
    # Try to get a non-existent station
    station_id = station_db.get_station_id(user_id, "Non-existent Station")
    assert station_id is None


def test_get_station(station_db):
    """Test getting a station by user ID and station ID."""
    # Create a user
    user_id = station_db.create_user("testuser")
    
    # Create a station
    station_id = station_db.create_station(user_id, "Test Station")
    
    # Get the station
    station = station_db.get_station(user_id, station_id)
    assert station is not None
    assert station.name == "Test Station"
    assert station.user_id == user_id


def test_get_station_not_found(station_db):
    """Test getting a non-existent station."""
    # Create a user
    user_id = station_db.create_user("testuser")
    
    # Try to get a non-existent station
    station = station_db.get_station(user_id, 999)
    assert station is None


def test_station_options_default(station_db):
    """Test getting default station options."""
    # Create a user and station
    user_id = station_db.create_user("testuser")
    station_id = station_db.create_station(user_id, "Test Station")
    
    # Get station options
    options = station_db.get_station_options(station_id)
    assert isinstance(options, StationOptions)
    assert options.replay_song_cooldown == 0
    assert options.replay_artist_downrank == 0.995
    assert options.ignore_live == False


def test_set_station_options(station_db):
    """Test setting station options."""
    # Create a user and station
    user_id = station_db.create_user("testuser")
    station_id = station_db.create_station(user_id, "Test Station")
    
    # Set custom options
    station_db.set_station_options(station_id, 50, 0.95, True)
    
    # Get and verify options
    options = station_db.get_station_options(station_id)
    assert options.replay_song_cooldown == 50
    assert options.replay_artist_downrank == 0.95
    assert options.ignore_live == True


def test_station_embedding(station_db):
    """Test setting and getting station embedding."""
    # Create a user and station
    user_id = station_db.create_user("testuser")
    station_id = station_db.create_station(user_id, "Test Station")
    
    # Test getting embedding when none exists
    embedding = station_db.get_station_embedding(station_id)
    assert embedding is None
    
    # Set an embedding
    test_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    station_db.set_station_embedding(station_id, test_embedding)
    
    # Get the embedding
    embedding = station_db.get_station_embedding(station_id)
    assert embedding is not None
    assert embedding == test_embedding


def test_add_track_to_history(station_db):
    """Test adding a track to history."""
    # Create a user and station
    user_id = station_db.create_user("testuser")
    station_id = station_db.create_station(user_id, "Test Station")

    with station_db.Session() as session:
        t = Track(
            artist="Test Artist",
            album="Test Album",
            track="Test Title",
            subsonic_id="song123"
        )
        session.add(t)
        session.commit()
        
    track = station_db.get_track_by_subsonic_id("song123")
        
    # Add a track to history
    track_history_id = station_db.add_track_to_or_update_history(
        station_id, track, False, 0
    )
    
    assert track_history_id is not None
    assert isinstance(track_history_id, int)
    assert track_history_id > 0


def test_update_track_in_history(station_db):
    """Test updating an existing track in history."""
    # Create a user and station
    user_id = station_db.create_user("testuser")
    station_id = station_db.create_station(user_id, "Test Station")

    with station_db.Session() as session:
        t1 = Track(
            artist="Test Artist",
            album="Test Album",
            track="Test Title",
            subsonic_id="song123"
        )
        session.add(t1)
        
        session.commit()
        
    track1 = station_db.get_track_by_subsonic_id("song123")
    
    # Add a track to history
    track_history_id1 = station_db.add_track_to_or_update_history(
        station_id, track1, False
    )
    
    # Update the same track (should return the same ID)
    track_history_id2 = station_db.add_track_to_or_update_history(
        station_id, track1, False
    )
    
    assert track_history_id1 == track_history_id2


def test_get_track_history(station_db):
    """Test getting track history."""
    # Create a user and station
    user_id = station_db.create_user("testuser")
    station_id = station_db.create_station(user_id, "Test Station")
    
    # Manually create track history entries with explicit timestamps to ensure proper ordering
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from boldaric.models.track_history import TrackHistory
    
    engine = create_engine(f"sqlite:///{station_db.db_path}")
    Session = sessionmaker(bind=engine)
    
    with Session() as session:
        # Create tracks with explicit timestamps
        base_time = datetime(2023, 1, 1, 12, 0, 0)

        track1 = Track(
            artist="Artist 1",
            album="Album 1",
            track="Title 1",
            subsonic_id="song1"
        )

        track2 = Track(
            artist="Artist 2",
            album="Album 2",
            track="Title 2",
            subsonic_id="song2"
        )

        track3 = Track(
            artist="Artist 3",
            album="Album 3",
            track="Title 3",
            subsonic_id="song3"
        )

        
        TrackHistory(
            station_id=station_id,
            track=track1,
            is_thumbs_downed=False,
            created_at=base_time,
            updated_at=base_time
        )
        
        TrackHistory(
            station_id=station_id,
            track=track2,
            is_thumbs_downed=False,
            created_at=base_time + timedelta(seconds=1),
            updated_at=base_time + timedelta(seconds=1)
        )
        
        TrackHistory(
            station_id=station_id,
            track=track3,
            is_thumbs_downed=False,
            created_at=base_time + timedelta(seconds=2),
            updated_at=base_time + timedelta(seconds=2)
        )
        
        session.add_all([track1, track2, track3])
        session.commit()
    
    # Get track history
    history = station_db.get_track_history(station_id, limit=2)
    assert len(history) == 2
    # Should be ordered by updated_at descending (most recent first)
    assert history[0].track.subsonic_id == "song3"
    assert history[1].track.subsonic_id == "song2"


def test_get_thumbs_downed_history(station_db):
    """Test getting thumbs downed track history."""
    # Create a user and station
    user_id = station_db.create_user("testuser")
    station_id = station_db.create_station(user_id, "Test Station")

    with station_db.Session() as session:
        t1 = Track(
            artist="Artist 1",
            album="Album 1",
            track="Title 1",
            subsonic_id="song1"
        )

        t2 = Track(
            artist="Artist 2",
            album="Album 2",
            track="Title 2",
            subsonic_id="song2"
        )

        t3 = Track(
            artist="Artist 3",
            album="Album 3",
            track="Title 3",
            subsonic_id="song3"
        )
        session.add_all([t1, t2, t3])
        session.commit()

    track1 = station_db.get_track_by_subsonic_id('song1')
    track2 = station_db.get_track_by_subsonic_id('song2')
    track3 = station_db.get_track_by_subsonic_id('song3')
    
    # Add some tracks to history, some thumbs downed
    import time
    station_db.add_track_to_or_update_history(
        station_id, track1, False
    )
    time.sleep(0.1)  # Ensure different timestamps
    station_db.add_track_to_or_update_history(
        station_id, track2, True
    )
    time.sleep(0.1)  # Ensure different timestamps
    station_db.add_track_to_or_update_history(
        station_id, track3, True
    )
    
    # Get thumbs downed history
    thumbs_downed = station_db.get_thumbs_downed_history(station_id)
    assert len(thumbs_downed) == 2
    # Should be ordered by created_at ascending (oldest first)
    assert thumbs_downed[0].track.subsonic_id == "song2"
    assert thumbs_downed[1].track.subsonic_id == "song3"

def test_load_station_history(station_db):
    """Test loading station history."""
    # Create a user, station, and track history
    user_id = station_db.create_user("testuser")
    station_id = station_db.create_station(user_id, "Test Station")

    t1 = create_track(station_db, 'Artist 1', 'Album 1', 'Title 1', 'song1')
    t2 = create_track(station_db, 'Artist 2', 'Album 2', 'Title 2', 'song2')
    
    station_db.add_track_to_or_update_history(
        station_id, t1, False
    )
    station_db.add_track_to_or_update_history(
        station_id, t2, True
    )
    
    # Load station history
    history, tracks, thumbs_downed = station_db.load_station_history(station_id)
    
    # Check that we got the expected data
    assert history is not None
    assert len(tracks) == 2
    assert len(thumbs_downed) == 1
    assert thumbs_downed[0].track.artist == "Artist 2"
    assert thumbs_downed[0].track.track == "Title 2"
