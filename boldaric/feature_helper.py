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

    # 3. General features (22D)
    embedding.extend([
        track.bpm,
        track.loudness,
        track.dynamic_complexity,
        track.energy_curve_mean,
        track.energy_curve_std,
        track.energy_curve_peak_count,
        track.chord_unique_chords,
        track.chord_change_rate,
        track.vocal_pitch_presence_ratio,
        track.vocal_pitch_segment_count,
        track.vocal_avg_pitch_duration,
        track.groove_danceability,
        track.groove_syncopation,
        track.groove_tempo_stability,
        track.mood_aggressiveness,
        track.mood_happiness,
        track.mood_partiness,
        track.mood_relaxedness,
        track.mood_sadness,
        track.spectral_character_brightness,
        track.spectral_character_contrast_mean,
        track.spectral_character_valley_std
    ])

    return embedding


##
# Convert a track to embeddings with the old (default) normalization
#  of each embedding. This generally works well.
def track_to_embeddings_default_normalization(track: Track) -> list[float]:
    """Convert the meteadata from a track into an embedding
    for chromadb using the old (default) normalization"""

    embedding = []

    # This is a frozen set of normalizations run across a large
    #  sample set (about 10k songs). This was generated using
    #  the `scripts/generate_default_normalization.py`.
    # Each item is a two item tuple of (mu, sigma).
    # We "freeze" this, and then apply it to each dimension
    #  (except we skip over the genre (first 128D), since it is special
    #  and doesn't use a global normalization.
    normalizations = np.array([
        (-579.0153, 93.115616), # mfcc1
        (121.02969, 35.89171), # mfcc2
        (-8.736084, 18.126032),
        (31.045422, 15.032619),
        (4.3233166, 10.162424),
        (5.8019357, 8.563145),
        (1.3605764, 7.2066274),
        (4.708241, 6.6627207),
        (0.7710379, 6.0194182),
        (0.9154733, 4.799032),
        (-2.0555038, 4.348381),
        (-0.38625118, 3.944581),
        (-2.1772165, 3.8194997), #mfcc 13
        (4.833678, 0.20692296), #bpm
        (7259.7393, 4252.6978), #loudness
        (3.5210261, 2.2940123), # dynamic complexity
        (25932.895, 17261.705), # energy curve mean
        (16136.202, 9384.273),
        (5740.474, 3310.3694),
        (2.548442, 0.36850905), # unique chords
        (2.689441, 0.0033397677),
        (0.60075575, 0.14680506), # vocal pitch presence ratio
        (221.23918, 124.92875),
        (0.038998336, 0.0214944), # vocal avg pitch duration
        (1.096557, 0.13374425), # groove danceability
        (0.03210547, 0.031888716),
        (0.9134095, 0.074802205),
        (0.16766348, 0.20404999), # mood aggressive
        (0.3512435, 0.30016428),
        (0.582958, 0.27398732),
        (0.29090673, 0.2647945),
        (0.7023456, 0.2528927), # mood sadness
        (-0.66693944, 0.10453378), # spectral brightness
        (-0.7030309, 0.031132152),
        (3.8848774, 2.24356) # spectral valley std
    ], dtype=np.float32)

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
    # We don't do global normalization here
    genre_norm = np.linalg.norm(genre_embeds)
    if genre_norm > 1e-9:
        genre_embeds = genre_embeds / genre_norm
    embedding.extend(genre_embeds.tolist())

    to_normalize = []
    
    # 2. MFCC features (13D)
    mfcc_means = np.array(track.mfcc_mean_array)[:13]
    to_normalize.extend(mfcc_means.tolist())

    # 3. General features (22D)
    to_normalize.extend([
        track.bpm,
        track.loudness,
        track.dynamic_complexity,
        track.energy_curve_mean,
        track.energy_curve_std,
        track.energy_curve_peak_count,
        track.chord_unique_chords,
        track.chord_change_rate,
        track.vocal_pitch_presence_ratio,
        track.vocal_pitch_segment_count,
        track.vocal_avg_pitch_duration,
        track.groove_danceability,
        track.groove_syncopation,
        track.groove_tempo_stability,
        track.mood_aggressiveness,
        track.mood_happiness,
        track.mood_partiness,
        track.mood_relaxedness,
        track.mood_sadness,
        track.spectral_character_brightness,
        track.spectral_character_contrast_mean,
        track.spectral_character_valley_std
    ])

    # normalize everything except
    #  the genres (first 128D), using the normalizations
    #  array
    to_normalize = np.array(to_normalize, dtype=np.float32)

    # seperate out the mu and sigma from each dimension
    #  of the frozen normalizations
    mus = normalizations[:, 0]
    sigmas = normalizations[:, 1]

    # apply log1p to
    #  bpm: dim 141
    #  unique_chords: dim 147
    #  vocal_avg_pitch_duration: dim 151
    bpm_idx = 141 - 128
    unique_chords_idx = 147 - 128
    vocal_avg_pitch_duration_idx = 151 - 128
    
    to_normalize[bpm_idx] = np.log1p(to_normalize[bpm_idx])
    to_normalize[unique_chords_idx] = np.log1p(to_normalize[unique_chords_idx])
    to_normalize[vocal_avg_pitch_duration_idx] = np.log1p(to_normalize[vocal_avg_pitch_duration_idx])

    normalized = (to_normalize - mus) / sigmas

    embedding.extend(normalized.tolist())
    
    return embedding
