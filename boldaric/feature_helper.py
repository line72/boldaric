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

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from .models.track import Track

# Keep track of the version
#  If we ever change normalization or embed
#  we'll update this
VERSION = 2


def track_to_embeddings(track: Track) -> list[float]:
    """Convert the meteadata from a track into an embedding
    for chromadb"""

    # !mwd - Unlike what I was doing previously in
    # features_to_embeddings, I am NOT normalizing any of these
    # values here.

    embedding = []

    # 1. Genre Embeddings (128D)
    genre_embeds = np.array(track.genre_embedding_array).flatten()
    # This shouldn't happen, but make sure we are at 128
    genre_embeds = (
        genre_embeds[:128]
        if len(genre_embeds) >= 128
        else np.pad(genre_embeds, (0, 128 - len(genre_embeds)))
    )
    embedding.extend(genre_embeds.tolist())

    # 2. MFCC features (13D)
    mfcc_means = np.array(track.mfcc_mean_array)[:13]
    embedding.extend(mfcc_means.tolist())

    # 3. Groove features (2D)
    danceability = track.groove_danceability
    tempo_stability = track.groove_tempo_stability
    embedding.extend([danceability, tempo_stability])

    # 4. Mood features (5D)
    mood_features = [
        track.mood_aggressiveness,
        track.mood_happiness,
        track.mood_partiness,
        track.mood_relaxedness,
        track.mood_sadness,
    ]
    embedding.extend(mood_features)

    return embedding


##
# Convert a track to embeddings with the old (default) normalization
#  of each embedding. This generally works well.
def track_to_embeddings_default_normalization(track: Track) -> list[float]:
    """Convert the meteadata from a track into an embedding
    for chromadb using the old (default) normalization"""

    embedding = []

    # 1. Genre Embeddings (128D)
    genre_embeds = np.array(track.genre_embedding_array).flatten()
    # This shouldn't happen, but make sure we are at 128
    genre_embeds = (
        genre_embeds[:128]
        if len(genre_embeds) >= 128
        else np.pad(genre_embeds, (0, 128 - len(genre_embeds)))
    )
    # Do some normalization, otherwise this
    #  may dominate other features in lookups
    genre_norm = np.linalg.norm(genre_embeds)
    if genre_norm > 1e-9:
        genre_embeds = genre_embeds / genre_norm
    embedding.extend(genre_embeds.tolist())

    # 2. MFCC features (13D)
    mfcc_means = np.array(track.mfcc_mean_array)[:13]
    # Normalize the entire MFCC vector rather than per-feature
    norm = np.linalg.norm(mfcc_means)
    if norm > 1e-9:
        mfcc_means = mfcc_means / norm
    embedding.extend(mfcc_means.tolist())

    # 3. Groove features (2D)
    danceability = track.groove_danceability
    tempo_stability = track.groove_tempo_stability
    embedding.extend([danceability, tempo_stability])

    # 4. Mood features (5D)
    mood_features = [
        track.mood_aggressiveness,
        track.mood_happiness,
        track.mood_partiness,
        track.mood_relaxedness,
        track.mood_sadness,
    ]
    # Apply sigmoid activation
    mood_features = 1 / (1 + np.exp(-np.array(mood_features)))
    embedding.extend(mood_features.tolist())

    # !mwd - My AI Agent suggest that I should have been
    #  normalizing the full embedding in additional to normalizing
    #  each feature. In earlier versions, I was not doing this. If
    #  you have an old database, you'll need to run the
    #  `scripts/fix-embedding-normalization.py` to migrate the
    #  embeddings.
    #
    # Normalize the full embedding vector
    embedding = np.array(embedding)
    embedding /= np.linalg.norm(embedding)

    return embedding.tolist()
