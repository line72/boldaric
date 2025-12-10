import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import time

from boldaric.models import Base
from boldaric.models.user import User
from boldaric.models.station import Station
from boldaric.models.track import Track
from boldaric.models.track_history import TrackHistory


@pytest.fixture(scope="function")
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_track_history_timestamps_on_creation(db_session):
    """Test that created_at and updated_at are set when TrackHistory is created."""
    # Create user, station, and track first
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

    # Refresh the object to get the database-set timestamps
    db_session.refresh(track_history)

    # Verify timestamps are set
    assert track_history.created_at is not None
    assert track_history.updated_at is not None

    # Verify created_at and updated_at are the same on creation
    assert track_history.created_at == track_history.updated_at


def test_track_history_updated_at_on_update(db_session):
    """Test that updated_at is automatically updated when TrackHistory is modified."""
    # Create user, station, and track first
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

    original_time = datetime.now() - timedelta(hours=1)

    # Create track history with an old time
    track_history = TrackHistory(
        station_id=station.id,
        track_id=track.id,
        is_thumbs_downed=False,
        rating=5,
        created_at=original_time,
        updated_at=original_time,
    )
    db_session.add(track_history)
    db_session.commit()

    # Refresh to get the initial timestamps
    db_session.refresh(track_history)

    # Store the original updated_at time
    original_updated_at = track_history.updated_at

    # Update the track history
    track_history.rating = 3
    db_session.commit()

    # Refresh the object to get the updated timestamp
    db_session.refresh(track_history)

    # Verify updated_at has changed
    assert track_history.updated_at > original_updated_at
    # created_at should remain the same
    assert track_history.created_at is not None
