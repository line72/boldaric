from sqlalchemy import Column, Integer, String, Float, DateTime, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func
import numpy as np
from ..models import Base

class TrackModel(Base):
    __tablename__ = 'tracks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    artist = Column(String)
    album = Column(String)
    track = Column(String)
    track_number = Column(Integer)
    genre = Column(String)
    subsonic_id = Column(String, unique=True)
    musicbrainz_artistid = Column(String)
    musicbrainz_albumid = Column(String)
    musicbrainz_trackid = Column(String)
    releasetype = Column(String)
    genre_embedding = Column(LargeBinary)
    mfcc_covariance = Column(LargeBinary)
    mfcc_mean = Column(LargeBinary)
    mfcc_temporal_variation = Column(Float)
    bpm = Column(Float)
    loudness = Column(Float)
    dynamic_complexity = Column(Float)
    energy_curve_mean = Column(Float)
    energy_curve_std = Column(Float)
    energy_curve_peak_count = Column(Integer)
    key_tonic = Column(String)
    key_scale = Column(String)
    key_confidence = Column(Float)
    chord_unique_chords = Column(Integer)
    chord_change_rate = Column(Float)
    vocal_pitch_presence_ratio = Column(Float)
    vocal_pitch_segment_count = Column(Integer)
    vocal_avg_pitch_duration = Column(Float)
    groove_beat_consistency = Column(Float)
    groove_danceability = Column(Float)
    groove_dnc_bpm = Column(Float)
    groove_syncopation = Column(Float)
    groove_tempo_stability = Column(Float)
    mood_aggressiveness = Column(Float)
    mood_happiness = Column(Float)
    mood_partiness = Column(Float)
    mood_relaxedness = Column(Float)
    mood_sadness = Column(Float)
    spectral_character_brightness = Column(Float)
    spectral_character_contrast_mean = Column(Float)
    spectral_character_valley_std = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    @hybrid_property
    def genre_embedding_array(self):
        """Get the genre embedding as a numpy array"""
        if self.genre_embedding is None:
            return None
        return np.frombuffer(self.genre_embedding, dtype=np.float64)
    
    @hybrid_property
    def mfcc_mean_array(self):
        """Get the mfcc mean as a numpy array"""
        if self.mfcc_mean is None:
            return None
        return np.frombuffer(self.mfcc_mean, dtype=np.float64)
    
    @hybrid_property
    def mfcc_covariance_array(self):
        """Get the mfcc covariance as a numpy array"""
        if self.mfcc_covariance is None:
            return None
        # Assuming a 13x13 covariance matrix for MFCC features
        return np.frombuffer(self.mfcc_covariance, dtype=np.float64).reshape((13, 13))
