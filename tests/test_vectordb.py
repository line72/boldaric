import os
import shutil
import tempfile
import numpy as np
import copy

import pytest

from boldaric.vectordb import VectorDB, TrackMetadata, CollectionType
from boldaric.models.track import Track
import boldaric.feature_helper

# Seed numpy for consistent test results
np.random.seed(42)


# Sample test data
SAMPLE_FEATURES = {
    "metadata": {
        "path": "/music/artist/album/track.mp3",
        "artist": "Test Artist",
        "album": "Test Album",
        "title": "Test Track",
        "date": "2023-01-01",
        "duration": 180,
        "sample_rate": 44100,
        "bit_depth": 16,
        "channels": 2,
        "genre": ["rock", "alternative"],
        "musicbrainz_releasetrackid": "mb-track-123",
    },
    "genre_embeddings": np.random.rand(128).tolist(),
    "mfcc": {"mean": [0.1] * 13},
    "groove": {"danceability": 0.7, "tempo_stability": 0.8},
    "mood": {
        "probabilities": {
            "aggressive": 0.2,
            "happy": 0.6,
            "relaxed": 0.1,
            "sad": 0.1,
            "party": 0.1,
        }
    },
    "loudness": -10.5,
    "dynamic_complexity": 0.6,
    "vocal": {"has_vocals": True},
    "spectral_character": {"brightness": 0.7},
    "key": {"key": "C", "scale": "major"},
    "genre": [
        {"name": "rock", "confidence": 0.8},
        {"name": "alternative", "confidence": 0.7},
    ],
}

SAMPLE_SUBSONIC_ID = "track-123"


def make_track(features):
    return Track(
        artist="Test Artist",
        album="Test Album",
        title="Test Track",
        genre_embedding=np.array(features["genre_embeddings"]).tobytes(),
        mfcc_mean=np.array(features["mfcc"]["mean"]).tobytes(),
        groove_danceability=features["groove"]["danceability"],
        groove_tempo_stability=features["groove"]["tempo_stability"],
        mood_aggressiveness=features["mood"]["probabilities"]["aggressive"],
        mood_happiness=features["mood"]["probabilities"]["happy"],
        mood_partiness=features["mood"]["probabilities"]["party"],
        mood_relaxedness=features["mood"]["probabilities"]["relaxed"],
        mood_sadness=features["mood"]["probabilities"]["sad"],
        loudness=features["loudness"],
        dynamic_complexity=features["dynamic_complexity"],
        spectral_character_brightness=features["spectral_character"]["brightness"],
        key_tonic=features["key"]["key"],
        key_scale=features["key"]["scale"],
    )


@pytest.fixture
def temp_db():
    # Create a temporary directory for the database
    temp_dir = tempfile.mkdtemp()
    db = VectorDB.build_from_path(temp_dir)
    yield db
    # Cleanup
    shutil.rmtree(temp_dir)


def test_add_track(temp_db):
    collection = CollectionType.OLD
    
    t = make_track(SAMPLE_FEATURES)
    temp_db.add_track(SAMPLE_SUBSONIC_ID, t)

    track = temp_db.get_track(collection, SAMPLE_SUBSONIC_ID)
    assert track is not None
    assert track["metadata"]["artist"] == "Test Artist"
    assert track["metadata"]["album"] == "Test Album"
    assert track["metadata"]["title"] == "Test Track"
    assert track["metadata"]["subsonic_id"] == SAMPLE_SUBSONIC_ID


def test_track_exists(temp_db):
    collection = CollectionType.OLD
    
    assert not temp_db.track_exists(collection, SAMPLE_SUBSONIC_ID)
    t = make_track(SAMPLE_FEATURES)
    temp_db.add_track(SAMPLE_SUBSONIC_ID, t)
    assert temp_db.track_exists(collection, SAMPLE_SUBSONIC_ID)


def test_query_similar(temp_db):
    collection = CollectionType.OLD
    
    # Add the base track
    t = make_track(SAMPLE_FEATURES)
    temp_db.add_track(SAMPLE_SUBSONIC_ID, t)

    # Add a similar track
    similar_features = copy.deepcopy(SAMPLE_FEATURES)
    similar_features["genre_embeddings"] = (
        np.array(SAMPLE_FEATURES["genre_embeddings"]) + np.random.normal(0, 0.01, 128)
    ).tolist()
    similar_features["mfcc"]["mean"] = [
        x + 0.01 for x in SAMPLE_FEATURES["mfcc"]["mean"]
    ]
    similar_features["groove"]["danceability"] += 0.01
    similar_features["groove"]["tempo_stability"] += 0.01
    similar_features["mood"]["probabilities"]["happy"] += 0.01
    similar_features["metadata"]["title"] = "Similar Track"
    t2 = make_track(similar_features)
    temp_db.add_track("similar-track", t2)

    # Add a very different track
    different_features = copy.deepcopy(SAMPLE_FEATURES)
    different_features["genre_embeddings"] = np.random.rand(128).tolist()
    different_features["mfcc"]["mean"] = [0.9] * 13
    different_features["groove"]["danceability"] = 0.1
    different_features["groove"]["tempo_stability"] = 0.1
    different_features["mood"]["probabilities"]["sad"] = 0.9
    similar_features["metadata"]["title"] = "Different Track"
    t3 = make_track(different_features)
    temp_db.add_track("different-track", t3)

    features = collection.value.track_to_embeddings(t)
    results = temp_db.query_similar(collection, features, n_results=2)

    assert len(results) == 2

    assert results[0]["id"] == SAMPLE_SUBSONIC_ID
    assert results[1]["id"] == "similar-track"
    assert (
        results[0]["similarity"] > results[1]["similarity"]
    ), "Results should be ordered by similarity"
