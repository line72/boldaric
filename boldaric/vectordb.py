# Copyright (c) 2025 Marcus Dillavou <line72@line72.net>
# Part of the Boldaric Project:
#  https://github.com/line72/boldaric
# Released under the AGPLv3 or later

# VectorDB is a wrapper around chroma.
#
# Everything is stored in a collection called
#  `audio_features`. Documents are stored using the subonic_id as the
#  primary key. This class allows inserting and updating track
#  embeddings, along with lookup, and similarity searches.

import json

import chromadb

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from typing import Dict, List, Optional
from pydantic import BaseModel

# Hard-coded to the number of dimension we extract
DIMENSIONS = 148

class TrackMetadata(BaseModel):
    path: str
    artist: str
    album: str
    title: str
    year: str
    rating: float = 0.0
    tagged_genres: List[str]
    predicted_genres: List[Dict]
    mood: Dict
    technical: Dict
    features: Dict
    musicbrainz_ids: Dict
    subsonic_id: str = None

class VectorDB:
    def __init__(self, path: str = "./chroma_db"):
        # This becomes a problem with multiple threads. So I am
        # switching to using the client-server mode:
        # https://docs.trychroma.com/docs/run-chroma/client-server
        #
        # Make sure the server is running by first doing:
        #  `chroma run --path /db_path`
        #
        collection_name = 'audio_features'
        
        self.client = chromadb.HttpClient(host='localhost',
                                          port=8000,
                                          settings=chromadb.Settings(
                                              anonymized_telemetry=False
                                          ))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "dimension": DIMENSIONS}
        )

    def add_track(self, subsonic_id: str, features: Dict):
        """Store a track's features"""
        meta = features.get('metadata', {})

        # Create a combined embedding
        embedding = []

        # 1. Genre Embeddings (128D)
        genre_embeds = np.array(features.get('genre_embeddings', np.seros(128))).flatten()
        # This shouldn't happen, but make sure we are at 128
        genre_embeds = genre_embeds[:128] if len(genre_embeds) >= 128 else np.pad(genre_embeds, (0, 128 - len(genre_embeds)))
        # Do some normalization, otherwise this
        #  may dominate other features in lookups
        genre_norm = np.linalg.norm(genre_embeds)
        if genre_norm > 1e-9:
            genre_embeds = genre_embeds / genre_norm
        embedding.extend(genre_embeds.tolist())

        # 2. MFCC features (13D)
        mfcc_stats = features.get('mfcc', {})
        mfcc_means = np.array(mfcc_stats.get('mean', np.zeros(13)))[:13]
        if len(mfcc_means) > 0:
            mfcc_min = np.min(mfcc_means)
            mfcc_max = np.max(mfcc_means)
            mfcc_range = mfcc_max - mfcc_min
            if mfcc_range > 1e-9:
                mfcc_means = (mfcc_means - mfcc_min) / mfcc_range
            else:
                mfcc_means = np.zeros_like(mfcc_means)
        else:
            mfcc_means = np.zeros(13)
        embedding.extend(mfcc_means.tolist())

        # 3. Groove features (2D)
        groove = features.get('groove', {})
        danceability = max(0, min(1, groove.get('danceability', 0.5)))
        tempo_stability = max(0, min(1, groove.get('tempo_stability', 0.5)))
        embedding.extend([danceability, tempo_stability])
        
        # 4. Mood features (5D)
        mood_probs = features.get('mood', {}).get('probabilities', {})
        mood_features = [
            mood_probs.get('aggressive', 0.5),
            mood_probs.get('happy', 0.5),
            mood_probs.get('party', 0.5),
            mood_probs.get('relaxed', 0.5),
            mood_probs.get('sad', 0.5)
        ]
        # Apply sigmoid activation
        mood_features = 1 / (1 + np.exp(-np.array(mood_features)))
        embedding.extend(mood_features.tolist())
        
        # 4. Mood features (5D)
        mood_probs = features.get('mood', {}).get('probabilities', {})
        mood_features = [
            mood_probs.get('aggressive', 0.5),
            mood_probs.get('happy', 0.5),
            mood_probs.get('party', 0.5),
            mood_probs.get('relaxed', 0.5),
            mood_probs.get('sad', 0.5)
        ]
        # Apply sigmoid activation
        mood_features = 1 / (1 + np.exp(-np.array(mood_features)))
        embedding.extend(mood_features.tolist())
        
        metadata = TrackMetadata(
            path=path,
            artist=meta.get('artist', 'Unknown Artist'),
            album=meta.get('album', 'Unknown Album'),
            title=meta.get('title', 'Unknown Track'),
            year=meta.get('date', '')[:4],
            tagged_genres=meta.get('genre', []),  
            predicted_genres=features.get('genre', []),
            mood=features.get('mood', {}).get('probabilities', {}),
            technical={
                'duration': meta.get('duration', 0),
                'sample_rate': meta.get('sample_rate', 44100),
                'bit_depth': meta.get('bit_depth', 16),
                'channels': meta.get('channels', 2),
                'loudness': features.get('loudness'),
                'dynamic_complexity': features.get('dynamic_complexity')
            },
            features={
                'rhythm': features.get('groove', {}),
                'harmony': features.get('key', {}),
                'timbral': features.get('spectral_character', {}),
                'mfcc': mfcc_stats,
                'vocal': features.get('vocal', {})
            },
            musicbrainz_ids={k:v for k,v in meta.items() if k.startswith('musicbrainz')},
            subsonic_id=subsonic_id
        ).dict()
        
        # Stringify list-based fields
        metadata['tagged_genres'] = '; '.join(metadata['tagged_genres'])
        metadata['predicted_genres'] = json.dumps(metadata['predicted_genres'])

        # Store musicbrainz IDs
        musicbrainz_trackid = metadata['musicbrainz_ids'].get('musicbrainz_releasetrackid', '')
        if isinstance(musicbrainz_trackid, str):
            musicbrainz_trackid = musicbrainz_trackid.split("'")[-1].split('"')[-1].strip()
        metadata['musicbrainz_trackid'] = musicbrainz_trackid

        # Remove complex structures
        metadata.pop('features', None)  
        metadata.pop('musicbrainz_ids', None)  
        
        # Flatten metadata
        mood_data = metadata.pop('mood', {})
        for key, value in mood_data.items():
            metadata[f'mood_{key}'] = float(value)
            
        tech_data = metadata.pop('technical', {})
        for key, value in tech_data.items():
            metadata[f'tech_{key}'] = float(value) if isinstance(value, (int, float)) else str(value)
            

        # Use the subsonic id as the doc id
        doc_id = subsonic_id
        self.collection.upsert(
            ids=doc_id,
            embeddings=[embedding],
            metadata=[metadata],
            documents=json.dumps(features)
        )
