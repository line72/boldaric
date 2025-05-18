import os
import shutil
import tempfile
import numpy as np
import copy

import pytest

from boldaric.vectordb import VectorDB, TrackMetadata

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
    "mood": {"probabilities": {"aggressive": 0.2, "happy": 0.6, "relaxed": 0.1, "sad": 0.1, "party": 0.1}},
    "loudness": -10.5,
    "dynamic_complexity": 0.6,
    "vocal": {"has_vocals": True},
    "spectral_character": {"brightness": 0.7},
    "key": {"key": "C", "scale": "major"},
    "genre": [{"name": "rock", "confidence": 0.8}, {"name": "alternative", "confidence": 0.7}],
}

SAMPLE_SUBSONIC_ID = "track-123"


@pytest.fixture
def temp_db():
    # Create a temporary directory for the database
    temp_dir = tempfile.mkdtemp()
    db = VectorDB.build_from_path(temp_dir)
    yield db
    # Cleanup
    shutil.rmtree(temp_dir)


def test_add_track(temp_db):
    temp_db.add_track(SAMPLE_SUBSONIC_ID, SAMPLE_FEATURES)

    track = temp_db.get_track(SAMPLE_SUBSONIC_ID)
    assert track is not None
    assert track["metadata"]["artist"] == "Test Artist"
    assert track["metadata"]["title"] == "Test Track"
    assert track["metadata"]["tagged_genres"] == "rock; alternative"
    assert track["metadata"]["musicbrainz_trackid"] == "mb-track-123"
    assert track["metadata"]["tech_duration"] == "180"
    assert track["metadata"]["tech_sample_rate"] == "44100"
    assert track["metadata"]["tech_bit_depth"] == "16"
    assert track["metadata"]["tech_channels"] == "2"
    assert track["metadata"]["tech_loudness"] == "-10.5"
    assert track["metadata"]["tech_dynamic_complexity"] == "0.6"
    assert track["metadata"]["mood_happy"] > 0.5


def test_track_exists(temp_db):
    assert not temp_db.track_exists(SAMPLE_SUBSONIC_ID)
    temp_db.add_track(SAMPLE_SUBSONIC_ID, SAMPLE_FEATURES)
    assert temp_db.track_exists(SAMPLE_SUBSONIC_ID)


def test_query_similar(temp_db):
    # Add the base track
    temp_db.add_track(SAMPLE_SUBSONIC_ID, SAMPLE_FEATURES)

    # Add a similar track
    similar_features = copy.deepcopy(SAMPLE_FEATURES)
    similar_features["genre_embeddings"] = (np.array(SAMPLE_FEATURES["genre_embeddings"]) + np.random.normal(0, 0.01, 128)).tolist()
    similar_features["mfcc"]["mean"] = [x + 0.01 for x in SAMPLE_FEATURES["mfcc"]["mean"]]
    similar_features["groove"]["danceability"] += 0.01
    similar_features["groove"]["tempo_stability"] += 0.01
    similar_features["mood"]["probabilities"]["happy"] += 0.01
    similar_features["metadata"]["title"] = "Similar Track"
    temp_db.add_track("similar-track", similar_features)

    # Add a very different track
    different_features = copy.deepcopy(SAMPLE_FEATURES)
    different_features["genre_embeddings"] = np.random.rand(128).tolist()
    different_features["mfcc"]["mean"] = [0.9] * 13
    different_features["groove"]["danceability"] = 0.1
    different_features["groove"]["tempo_stability"] = 0.1
    different_features["mood"]["probabilities"]["sad"] = 0.9
    similar_features["metadata"]["title"] = "Different Track"
    temp_db.add_track("different-track", different_features)

    results = temp_db.query_similar(SAMPLE_FEATURES, n_results=2)
    
    assert len(results) == 2
    
    assert results[0]["id"] == SAMPLE_SUBSONIC_ID
    assert results[1]["id"] == "similar-track"
    assert results[0]["similarity"] > results[1]["similarity"], "Results should be ordered by similarity"

    # Check contributions
    for result in results:
        contribs = result["feature_contributions"]
        assert all(0 <= contribs[feat] <= 100 for feat in contribs)
        sims = result["component_similarities"]
        assert all(0 <= sims[feat] <= 1 for feat in sims)
