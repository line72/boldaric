import numpy as np
import pytest
from pathlib import Path

from boldaric.extractor import extract_features

# Test audio file path - this should be a real audio file
# To run tests, you'll need to provide a real audio file at this path
TEST_AUDIO_FILE = "tests/test.mp3"

@pytest.fixture
def sample_audio_file():
    yield TEST_AUDIO_FILE

def test_extract_features_structure(sample_audio_file):
    """Test that extract_features returns features with expected structure"""
    features = extract_features(sample_audio_file)
    
    # Check that we have the main feature categories
    expected_keys = {
        'metadata', 'bpm', 'loudness', 'dynamic_complexity',
        'energy_curve', 'key', 'chord_stability', 'vocal',
        'mfcc', 'spectral_character', 'groove', 'mood', 'genre'
    }
    
    assert isinstance(features, dict)
    assert features.keys() == expected_keys
    
    # Check that genre predictions have label-score pairs
    assert all(isinstance(genre, dict) and 'label' in genre and 'score' in genre 
              for genre in features['genre'])
    
    # Check that mood probabilities are in [0, 1] range
    assert all(0 <= prob <= 1 for prob in features['mood']['probabilities'].values())
    
    # Check that MFCC features have mean and covariance
    assert 'mean' in features['mfcc']
    assert 'covariance' in features['mfcc']
    
    # Check that groove features have expected components
    groove_keys = {'danceability', 'tempo_stability', 'beat_confidence', 'syncopation', 'dnc_bpm', 'beat_consistency'}
    assert features['groove'].keys() == groove_keys


def test_extract_features_with_nonexistent_file():
    """Test handling of nonexistent audio files"""
    with pytest.raises(Exception):
        extract_features("nonexistent_file.mp3")


def test_extract_features_with_invalid_file(tmp_path):
    """Test handling of invalid audio files"""
    # Create a text file that's not a valid audio file
    invalid_file = tmp_path / "invalid.txt"
    invalid_file.write_text("this is not audio data")
    
    with pytest.raises(Exception):
        extract_features(str(invalid_file))


def test_metadata_extraction(sample_audio_file):
    """Test that metadata is extracted correctly"""
    features = extract_features(sample_audio_file)
    metadata = features['metadata']
    
    # Check that we have basic metadata fields
    required_metadata = {
        'path', 'duration', 'audio_length'
    }
    assert metadata.keys() >= required_metadata  # Using >= to check subset
    
    # Check that path is absolute
    assert Path(metadata['path']).is_absolute()
    
    # Check that duration is a positive number
    assert isinstance(metadata['duration'], float)
    assert metadata['duration'] > 0


def test_extract_genre_returns_embeddings():
    """Test that genre extraction returns embeddings"""
    # This test is a bit tricky since we need to mock audio data
    # We'll test the structure of the output when we have valid audio
    pass  # TODO: Implement with proper audio mocking if needed
