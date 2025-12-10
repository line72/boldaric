import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from boldaric.models import Base
from boldaric.models.user import User
from boldaric.models.station import Station
from boldaric.models.track_history import TrackHistory
from boldaric.models.track import Track


@pytest.fixture(scope="function")
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_user_creation(db_session):
    """Test creating a user."""
    user = User(username="testuser")
    db_session.add(user)
    db_session.commit()

    # Verify user was created
    retrieved = db_session.query(User).filter_by(username="testuser").first()
    assert retrieved is not None
    assert retrieved.username == "testuser"
    assert retrieved.id is not None


def test_user_unique_username(db_session):
    """Test that usernames are unique."""
    user1 = User(username="testuser")
    user2 = User(username="testuser")

    db_session.add(user1)
    db_session.commit()

    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_station_creation(db_session):
    """Test creating a station."""
    # First create a user
    user = User(username="testuser")
    db_session.add(user)
    db_session.commit()

    # Create a station
    station = Station(
        user_id=user.id,
        name="Test Station",
        replay_song_cooldown=10,
        replay_artist_downrank=0.95,
        ignore_live=True,
    )
    db_session.add(station)
    db_session.commit()

    # Verify station was created
    retrieved = db_session.query(Station).filter_by(name="Test Station").first()
    assert retrieved is not None
    assert retrieved.user_id == user.id
    assert retrieved.name == "Test Station"
    assert retrieved.replay_song_cooldown == 10
    assert retrieved.replay_artist_downrank == 0.95
    assert retrieved.ignore_live is True


def test_track_history_creation(db_session):
    """Test creating track history."""
    # Create user, station, and track
    user = User(username="testuser")
    db_session.add(user)
    db_session.commit()

    station = Station(user_id=user.id, name="Test Station")
    db_session.add(station)
    db_session.commit()

    track = Track(
        artist="Test Artist",
        album="Test Album",
        track="Test Title",
        subsonic_id="song123",
    )
    db_session.add(track)
    db_session.commit()

    # Create track history
    track_history = TrackHistory(
        station_id=station.id, track_id=track.id, is_thumbs_downed=False, rating=5
    )
    db_session.add(track_history)
    db_session.commit()

    # Verify track history was created
    retrieved = db_session.query(TrackHistory).first()
    assert retrieved is not None
    assert retrieved.station_id == station.id
    assert retrieved.track_id == track.id
    assert retrieved.is_thumbs_downed is False
    assert retrieved.rating == 5


def test_user_station_relationship(db_session):
    """Test the user-station relationship."""
    user = User(username="testuser")
    db_session.add(user)
    db_session.commit()

    station1 = Station(user_id=user.id, name="Station 1")
    station2 = Station(user_id=user.id, name="Station 2")
    db_session.add_all([station1, station2])
    db_session.commit()

    # Verify relationships
    retrieved_user = db_session.query(User).filter_by(username="testuser").first()
    assert len(retrieved_user.stations) == 2
    assert station1 in retrieved_user.stations
    assert station2 in retrieved_user.stations


def test_station_track_history_relationship(db_session):
    """Test the station-track history relationship."""
    # Create user, station, and track
    user = User(username="testuser")
    db_session.add(user)
    db_session.commit()

    station = Station(user_id=user.id, name="Test Station")
    db_session.add(station)
    db_session.commit()

    track = Track(
        artist="Test Artist",
        album="Test Album",
        track="Test Title",
        subsonic_id="song123",
    )
    db_session.add(track)
    db_session.commit()

    # Create track histories
    track1 = TrackHistory(
        station_id=station.id, track_id=track.id, is_thumbs_downed=False, rating=3
    )
    track2 = TrackHistory(
        station_id=station.id, track_id=track.id, is_thumbs_downed=False, rating=4
    )
    db_session.add_all([track1, track2])
    db_session.commit()

    # Verify relationships
    retrieved_station = db_session.query(Station).first()
    assert len(retrieved_station.track_history) == 2
    assert track1 in retrieved_station.track_history
    assert track2 in retrieved_station.track_history

    # Verify track relationship
    retrieved_track_history = db_session.query(TrackHistory).first()
    assert retrieved_track_history.track == track
