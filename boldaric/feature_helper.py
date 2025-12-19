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

from typing import Protocol

# Keep track of the version
#  If we ever change normalization or embed
#  we'll update this
VERSION = 2


class FeatureHelper(Protocol):
    def name() -> str: ...

    def dimensions() -> int: ...

    def space() -> str: ...

    def track_to_embeddings(track: Track) -> list[float]: ...


class DefaultFeatureHelper(FeatureHelper):
    @staticmethod
    def name():
        return "default"

    @staticmethod
    def dimensions():
        return 163

    @staticmethod
    def space():
        return "cosine"

    @staticmethod
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


class NormalizedFeatureHelper(FeatureHelper):
    @staticmethod
    def name():
        return "normalized"

    @staticmethod
    def dimensions():
        return 163

    @staticmethod
    def space():
        return "cosine"

    ##
    # Convert a track to embeddings with a normalization
    #  of each embedding.
    @staticmethod
    def track_to_embeddings(track: Track) -> list[float]:
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


class OldFeatureHelper(FeatureHelper):
    @staticmethod
    def name():
        return "old"

    @staticmethod
    def dimensions():
        return 148

    @staticmethod
    def space():
        return "cosine"

    ##
    # Convert a track to embeddings with the old (default) normalization
    #  of each embedding. This generally works well.
    @staticmethod
    def track_to_embeddings(track: Track) -> list[float]:
        """
        Convert the meteadata from a track into an embedding
        for chromadb using the old (default) normalization.

        Note, this only has 148 dimension!
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


class MoodFeatureHelper(FeatureHelper):
    @staticmethod
    def name():
        return "mood"

    @staticmethod
    def dimensions():
        return 163

    @staticmethod
    def space():
        return "ip"

    @staticmethod
    def track_to_embeddings(track: Track) -> list[float]:
        """
        Convert the metadata from a track into an embedding.

        Use the default_normalization with frozen normalization,
        then apply fisher weights for MOOD. These were pre-calulated
        using a sample playlist and the `analyze_similarities` script
        """
        FISHER_MOOD_WEIGHTS = [
            0.129202201962471,
            0.061582084745168686,
            0.22741712629795074,
            0.0032683603931218386,
            0.35062074661254883,
            0.002560896100476384,
            0.020857149735093117,
            0.0012634028680622578,
            0.0016091002617031336,
            0.035368986427783966,
            0.08381995558738708,
            0.020589224994182587,
            0.09401828050613403,
            0.1503506749868393,
            0.07833821326494217,
            0.04323480650782585,
            0.08986081928014755,
            0.026697685942053795,
            0.06531988829374313,
            0.07651636749505997,
            0.022830279543995857,
            0.35526126623153687,
            0.0009801835985854268,
            0.007414339110255241,
            0.005807399749755859,
            0.12089739739894867,
            0.22750931978225708,
            0.06707814335823059,
            0.017034165561199188,
            0.12129467725753784,
            0.0073053971864283085,
            0.24509887397289276,
            0.2959902882575989,
            0.12467845529317856,
            0.1136629581451416,
            0.16148343682289124,
            0.015132369473576546,
            0.00013772824604529887,
            0.0035062283277511597,
            0.029742320999503136,
            0.08335233479738235,
            0.08561030775308609,
            0.010763860307633877,
            0.028887460008263588,
            0.0002497877285350114,
            0.2727832794189453,
            0.07859191298484802,
            0.016918789595365524,
            0.018112769350409508,
            0.031046871095895767,
            0.03677638992667198,
            0.004691190551966429,
            0.14001333713531494,
            0.09472053498029709,
            0.023236596956849098,
            0.06310927122831345,
            0.0026977350935339928,
            4.070082650287077e-05,
            0.17571355402469635,
            0.025470299646258354,
            0.061452943831682205,
            0.025305984541773796,
            0.1359826922416687,
            0.02218594402074814,
            2.200073686253745e-05,
            0.014718348160386086,
            0.011653229594230652,
            0.05055565387010574,
            0.006435537710785866,
            0.012141639366745949,
            0.008221003226935863,
            0.01329215057194233,
            0.02148394286632538,
            0.30028238892555237,
            4.79408263345249e-05,
            0.006176487077027559,
            0.05508613586425781,
            0.011921648867428303,
            0.1753917634487152,
            0.04168444499373436,
            0.0006224323296919465,
            0.4145091474056244,
            0.05671157315373421,
            0.17093577980995178,
            0.01646818406879902,
            0.21349488198757172,
            0.059036124497652054,
            0.15072989463806152,
            0.027626095339655876,
            0.12759670615196228,
            0.0018260611686855555,
            0.02590220794081688,
            0.07879143953323364,
            0.024775033816695213,
            0.23906366527080536,
            0.00706592807546258,
            0.07393775880336761,
            0.06412488222122192,
            0.021034767851233482,
            0.05499451979994774,
            0.0009558091405779123,
            0.0026413516607135534,
            0.17956547439098358,
            0.10647899657487869,
            0.0033641797490417957,
            0.10384882986545563,
            0.007159812841564417,
            0.10350583493709564,
            0.27253055572509766,
            0.13483844697475433,
            0.004278948996216059,
            0.04662701115012169,
            0.02008267678320408,
            0.046044547110795975,
            0.037585362792015076,
            0.2631933093070984,
            0.01923268288373947,
            0.014647554606199265,
            0.022597553208470345,
            0.0143570676445961,
            0.005850190296769142,
            0.10513848066329956,
            0.00025887630181387067,
            0.26781943440437317,
            0.06676195561885834,
            0.12167403846979141,
            0.022740505635738373,
            0.025098269805312157,
            0.16193793714046478,
            0.06371151655912399,
            0.019766172394156456,
            0.09489312767982483,
            0.0044720969162881374,
            2.6856616386794485e-05,
            0.00016245266306214035,
            0.040252383798360825,
            0.0035731031093746424,
            0.07892274856567383,
            0.0783076286315918,
            0.1454896330833435,
            0.0018857793183997273,
            0.057164400815963745,
            0.9999987483024597,
            0.01822609081864357,
            0.2786405384540558,
            0.1455652117729187,
            0.5864867568016052,
            0.10014627873897552,
            0.04754767566919327,
            0.0025934926234185696,
            0.86341792345047,
            0.0073740435764193535,
            0.05536904186010361,
            0.059483710676431656,
            0.10198584944009781,
            0.02626902051270008,
            3.837543772533536e-06,
            0.5911667943000793,
            0.00020143001165706664,
            0.19053223729133606,
            0.11953098326921463,
            0.0036115252878516912,
            0.09334176778793335,
        ]

        embedding = NormalizedFeatureHelper.track_to_embeddings(track)

        embedding = np.array(embedding) * np.array(FISHER_MOOD_WEIGHTS)

        return embedding.tolist()


class GenreFeatureHelper(FeatureHelper):
    @staticmethod
    def name():
        return "genre"

    @staticmethod
    def dimensions():
        return 128

    @staticmethod
    def space():
        return "l2"

    @staticmethod
    def track_to_embeddings(track: Track) -> list[float]:
        """
        Convert the metadata from a track into an embedding.

        Use the default_normalization with frozen normalization,
        then apply fisher weights for GENRE. We basically remove
        all other weights
        """
        embedding = DefaultFeatureHelper.track_to_embeddings(track)[:128]

        return embedding
