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

DIMENSIONS = 163


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
    embedding.extend(
        [
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
            track.spectral_character_valley_std,
        ]
    )

    return embedding


##
# Convert a track to embeddings with a normalization
#  of each embedding.
def track_to_embeddings_default_normalization(track: Track) -> list[float]:
    """
    Convert the meteadata from a track into an embedding
    for chromadb using normalization. The normalization values
    come from a sample set (about 10k) songs and a frozen
    """

    embedding = []

    # This is a frozen set of normalizations run across a large
    #  sample set (about 10k songs). This was generated using
    #  the `scripts/generate_default_normalization.py`.
    # Each item is a two item tuple of (mu, sigma).
    # We "freeze" this, and then apply it to each dimension
    #  (except we skip over the genre (first 128D), since it is special
    #  and doesn't use a global normalization.
    normalizations = np.array(
        [
            (-579.0153, 93.115616),  # mfcc1
            (121.02969, 35.89171),  # mfcc2
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
            (-2.1772165, 3.8194997),  # mfcc 13
            (4.833678, 0.20692296),  # bpm
            (7259.7393, 4252.6978),  # loudness
            (3.5210261, 2.2940123),  # dynamic complexity
            (25932.895, 17261.705),  # energy curve mean
            (16136.202, 9384.273),
            (5740.474, 3310.3694),
            (2.548442, 0.36850905),  # unique chords
            (2.689441, 0.0033397677),
            (0.60075575, 0.14680506),  # vocal pitch presence ratio
            (221.23918, 124.92875),
            (0.038998336, 0.0214944),  # vocal avg pitch duration
            (1.096557, 0.13374425),  # groove danceability
            (0.03210547, 0.031888716),
            (0.9134095, 0.074802205),
            (0.16766348, 0.20404999),  # mood aggressive
            (0.3512435, 0.30016428),
            (0.582958, 0.27398732),
            (0.29090673, 0.2647945),
            (0.7023456, 0.2528927),  # mood sadness
            (-0.66693944, 0.10453378),  # spectral brightness
            (-0.7030309, 0.031132152),
            (3.8848774, 2.24356),  # spectral valley std
        ],
        dtype=np.float32,
    )

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
    to_normalize.extend(
        [
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
            track.spectral_character_valley_std,
        ]
    )

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
    to_normalize[vocal_avg_pitch_duration_idx] = np.log1p(
        to_normalize[vocal_avg_pitch_duration_idx]
    )

    normalized = (to_normalize - mus) / sigmas

    embedding.extend(normalized.tolist())

    return embedding


##
# Convert a track to embeddings with the old (default) normalization
#  of each embedding. This generally works well.
def track_to_embeddings_old_normalization(track: Track) -> list[float]:
    """
    Convert the meteadata from a track into an embedding
    for chromadb using the old (default) normalization
    """

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

    # Use some 0s
    embedding.extend(
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]
    )

    # 3. Groove features (2D)
    danceability = track.groove_danceability
    tempo_stability = track.groove_tempo_stability
    embedding.extend([danceability, 0.0, tempo_stability])

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

    # spectral
    embedding.extend([0.0, 0.0, 0.0])

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


def track_to_embeddings_mood(track: Track) -> list[float]:
    """
    Convert the metadata from a track into an embedding.

    Use the default_normalization with frozen normalization,
    then apply fisher weights for MOOD. These were pre-calulated
    using a sample playlist and the `analyze_similarities` script
    """
    FISHER_MOOD_WEIGHTS = [
        0.006938213482499123,
        0.01691255159676075,
        0.00043675352935679257,
        0.009097804315388203,
        1.0140853490270274e-08,
        0.0026314794085919857,
        0.0005753539735451341,
        0.0012278285576030612,
        4.7557246034557465e-06,
        6.446203997256816e-07,
        3.800491685979068e-05,
        0.003338765585795045,
        0.0003763399727176875,
        0.0072518521919846535,
        0.005285595543682575,
        0.0026449616998434067,
        0.0024752779863774776,
        0.006110985763370991,
        0.003369000041857362,
        0.0006816036184318364,
        0.0019064985681325197,
        0.0007628947496414185,
        0.04204279184341431,
        0.004446547478437424,
        0.004471648950129747,
        0.006576004903763533,
        0.005399028770625591,
        0.0015658275224268436,
        0.0017970410408452153,
        0.0010636887745931745,
        0.007111971732228994,
        0.002115919254720211,
        0.00013074619346298277,
        0.0006467615021392703,
        0.00017010646115522832,
        0.000713168818037957,
        0.0031191108282655478,
        0.006182785611599684,
        0.00015866744797676802,
        0.0047146533615887165,
        0.00405226880684495,
        0.0003134129801765084,
        0.0008446173742413521,
        0.0029893890023231506,
        0.02174244448542595,
        0.0147476177662611,
        0.002375182695686817,
        0.0015550859970971942,
        0.0001587401784490794,
        0.0007259447011165321,
        2.7610069082584232e-05,
        0.0006799008115194738,
        8.319457992911339e-05,
        3.7243225960992277e-06,
        1.0101826042330231e-08,
        0.0003001757140737027,
        0.0026371912099421024,
        8.247600635513663e-05,
        0.00019153972971253097,
        0.0008783024386502802,
        0.0034290850162506104,
        0.0008937655948102474,
        4.8570354920229875e-06,
        6.501316875073826e-06,
        0.0014285544166341424,
        0.00014381075743585825,
        0.0007289616041816771,
        0.00018207970424555242,
        0.0038742786273360252,
        0.009246313013136387,
        0.001484170090407133,
        0.0008300208137370646,
        0.0005066970479674637,
        0.006664961110800505,
        0.0012352349003776908,
        5.067134043201804e-05,
        0.0002587891067378223,
        0.0011079778196290135,
        0.003627171739935875,
        0.0016519231721758842,
        0.0038383237551897764,
        0.0003486966888885945,
        0.0018113045953214169,
        0.000980411539785564,
        0.004562864080071449,
        0.00027740804944187403,
        0.0005501576233655214,
        0.0020481881219893694,
        0.00016325499746017158,
        0.00022207752044778317,
        0.000211899503483437,
        0.00014665017079096287,
        0.0004868415417149663,
        0.004932377487421036,
        0.0004608537128660828,
        0.010170121677219868,
        0.0015000930288806558,
        0.00975625030696392,
        0.0006490943487733603,
        0.003326773177832365,
        0.0016529877902939916,
        0.003357604378834367,
        0.004509845282882452,
        5.260906618786976e-05,
        0.00013990182196721435,
        3.407012627576478e-06,
        0.005453909281641245,
        0.0006030283984728158,
        0.0003330861800350249,
        0.0012026377953588963,
        0.00442945072427392,
        0.00031194675830192864,
        0.0001351710525341332,
        0.00025770056527107954,
        0.0013238962274044752,
        0.0031853739637881517,
        0.0016476258169859648,
        0.0004885009257122874,
        5.776649345534679e-07,
        4.016308594145812e-05,
        0.0008941921405494213,
        0.0007197493687272072,
        0.0027327120769768953,
        0.061892181634902954,
        0.002256479812785983,
        1.0,
        0.0019466594094410539,
        0.003313296940177679,
        0.0014590853825211525,
        0.002963508013635874,
        0.023049402981996536,
        0.00016600544040556997,
        2.5276887754444033e-05,
        0.003984992858022451,
        0.0013784741749987006,
        0.0006758780800737441,
        0.0011189457727596164,
        0.0003311133768875152,
        0.00010537223715800792,
        1.8302790749658016e-06,
        0.0016220208490267396,
        0.0023704287596046925,
        0.0007351522799581289,
        0.007709290366619825,
        0.00034467235673218966,
        0.045494478195905685,
        0.0010364946210756898,
        0.0011215574340894818,
        0.000833101395983249,
        0.0021439609117805958,
        0.0004053669690620154,
        0.0005410683806985617,
        1.92160969163524e-05,
        0.0002948514884337783,
        0.0002595003170426935,
        0.00010352600656915456,
        0.0013731311773881316,
        0.0003748375456780195,
        0.004689686466008425,
        2.945186679426115e-05,
        0.16701973974704742,
        0.003247103886678815,
        0.0006689989822916687,
    ]

    embedding = track_to_embeddings_default_normalization(track)

    embedding = np.array(embedding) * np.array(FISHER_MOOD_WEIGHTS)
    
    return embedding.tolist()

def track_to_embeddings_genre(track: Track) -> list[float]:
    """
    Convert the metadata from a track into an embedding.

    Use the default_normalization with frozen normalization,
    then apply fisher weights for GENRE. We basically remove
    all other weights
    """
    FISHER_GENRE_WEIGHTS = [1.0]*128 + [0.0]*35

    embedding = track_to_embeddings_default_normalization(track)

    embedding = np.array(embedding) * np.array(FISHER_GENRE_WEIGHTS)
    
    return embedding.tolist()
    
