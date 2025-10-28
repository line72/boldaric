from dataclasses import dataclass, field
from typing import List, Optional, Union
from datetime import datetime
import numpy as np


@dataclass
class Track:
    tid: int = 0
    artist: str = ""
    album: str = ""
    track: str = ""
    track_number: int = 0
    genre: str = ""
    subsonic_id: str = ""
    musicbrainz_artistid: str = ""
    musicbrainz_albumid: str = ""
    musicbrainz_trackid: str = ""
    releasetype: str = ""
    genre_embedding: Optional[bytes] = None
    mfcc_covariance: Optional[bytes] = None
    mfcc_mean: Optional[bytes] = None
    mfcc_temporal_variation: float = 0.0
    bpm: float = 0.0
    loudness: float = 0.0
    dynamic_complexity: float = 0.0
    energy_curve_mean: float = 0.0
    energy_curve_std: float = 0.0
    energy_curve_peak_count: int = 0
    key_tonic: str = ""
    key_scale: str = ""
    key_confidence: float = 0.0
    chord_unique_chords: int = 0
    chord_change_rate: float = 0.0
    vocal_pitch_presence_ratio: float = 0.0
    vocal_pitch_segment_count: int = 0
    vocal_avg_pitch_duration: float = 0.0
    groove_beat_consistency: float = 0.0
    groove_danceability: float = 0.0
    groove_dnc_bpm: float = 0.0
    groove_syncopation: float = 0.0
    groove_tempo_stability: float = 0.0
    mood_aggressiveness: float = 0.0
    mood_happiness: float = 0.0
    mood_partiness: float = 0.0
    mood_relaxedness: float = 0.0
    mood_sadness: float = 0.0
    spectral_character_brightness: float = 0.0
    spectral_character_contrast_mean: float = 0.0
    spectral_character_valley_std: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
