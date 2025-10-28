import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from boldaric.models import Base
from boldaric.models.user import User
from boldaric.models.station import Station
from boldaric.models.track_history import TrackHistory
from boldaric.models.embedding_history import EmbeddingHistory


@pytest.fixture(scope="function")
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:')
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
        ignore_live=True
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
    # Create user and station
    user = User(username="testuser")
    db_session.add(user)
    db_session.commit()
    
    station = Station(user_id=user.id, name="Test Station")
    db_session.add(station)
    db_session.commit()
    
    # Create track history
    track_history = TrackHistory(
        station_id=station.id,
        subsonic_id="song123",
        artist="Test Artist",
        title="Test Title",
        album="Test Album",
        is_thumbs_downed=False
    )
    db_session.add(track_history)
    db_session.commit()
    
    # Verify track history was created
    retrieved = db_session.query(TrackHistory).first()
    assert retrieved is not None
    assert retrieved.station_id == station.id
    assert retrieved.subsonic_id == "song123"
    assert retrieved.artist == "Test Artist"
    assert retrieved.title == "Test Title"
    assert retrieved.album == "Test Album"
    assert retrieved.is_thumbs_downed is False


def test_embedding_history_creation(db_session):
    """Test creating embedding history."""
    # Create user, station, and track history
    user = User(username="testuser")
    db_session.add(user)
    db_session.commit()
    
    station = Station(user_id=user.id, name="Test Station")
    db_session.add(station)
    db_session.commit()
    
    track_history = TrackHistory(
        station_id=station.id,
        subsonic_id="song123",
        artist="Test Artist",
        title="Test Title",
        album="Test Album"
    )
    db_session.add(track_history)
    db_session.commit()
    
    # Create embedding history
    embedding_data = [0.1, 0.2, 0.3, 0.4, 0.5]
    embedding_history = EmbeddingHistory(
        station_id=station.id,
        track_history_id=track_history.id,
        embedding=embedding_data,
        rating=5
    )
    db_session.add(embedding_history)
    db_session.commit()
    
    # Verify embedding history was created
    retrieved = db_session.query(EmbeddingHistory).first()
    assert retrieved is not None
    assert retrieved.station_id == station.id
    assert retrieved.track_history_id == track_history.id
    assert retrieved.embedding == embedding_data
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
    # Create user and station
    user = User(username="testuser")
    db_session.add(user)
    db_session.commit()
    
    station = Station(user_id=user.id, name="Test Station")
    db_session.add(station)
    db_session.commit()
    
    # Create track histories
    track1 = TrackHistory(
        station_id=station.id,
        subsonic_id="song1",
        artist="Artist 1",
        title="Title 1",
        album="Album 1"
    )
    track2 = TrackHistory(
        station_id=station.id,
        subsonic_id="song2",
        artist="Artist 2",
        title="Title 2",
        album="Album 2"
    )
    db_session.add_all([track1, track2])
    db_session.commit()
    
    # Verify relationships
    retrieved_station = db_session.query(Station).first()
    assert len(retrieved_station.track_history) == 2
    assert track1 in retrieved_station.track_history
    assert track2 in retrieved_station.track_history


def test_station_embedding_history_relationship(db_session):
    """Test the station-embedding history relationship."""
    # Create user, station, and track history
    user = User(username="testuser")
    db_session.add(user)
    db_session.commit()
    
    station = Station(user_id=user.id, name="Test Station")
    db_session.add(station)
    db_session.commit()
    
    track_history = TrackHistory(
        station_id=station.id,
        subsonic_id="song123",
        artist="Test Artist",
        title="Test Title",
        album="Test Album"
    )
    db_session.add(track_history)
    db_session.commit()
    
    # Create embedding histories
    embedding1 = EmbeddingHistory(
        station_id=station.id,
        track_history_id=track_history.id,
        embedding=[0.1, 0.2],
        rating=5
    )
    embedding2 = EmbeddingHistory(
        station_id=station.id,
        track_history_id=track_history.id,
        embedding=[0.3, 0.4],
        rating=3
    )
    db_session.add_all([embedding1, embedding2])
    db_session.commit()
    
    # Verify relationships
    retrieved_station = db_session.query(Station).first()
    assert len(retrieved_station.embedding_history) == 2
    assert embedding1 in retrieved_station.embedding_history
    assert embedding2 in retrieved_station.embedding_history
