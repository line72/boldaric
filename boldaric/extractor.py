# Copyright (c) 2025 Marcus Dillavou <line72@line72.net>
# Part of the Boldaric Project:
#  https://github.com/line72/boldaric
# Released under the AGPLv3 or later

# This module uses (essentia + tensorflow) to run various machine
# learning algorithms on a song and produce a set of features. Those
# features get normalized and turn into embeddings we can do
# similarity searches on.

import logging
import os

import numpy as np
from mutagen import File

from importlib.resources import files

from . import labels


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def extract_features(file_path):
    # disable logging
    logging.getLogger("tensorflow").setLevel(logging.ERROR)
    logging.getLogger("essentia").setLevel(logging.ERROR)
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
    os.environ["ESSENTIA_LOG_LEVEL"] = "ERROR"

    # Wait to load these as it slows down
    #  starting the program
    # Suppress Essentia's internal logging
    import essentia

    # disable logging in all the dumb possible ways
    essentia.log.infoActive = False
    essentia.log.warningActive = False

    import essentia.standard as es

    # Load audio first so we have audio_44_1k variable
    # We load with different sample rates as different models were trained
    #  with data at specific sample rates.
    # For example, The Effnet model expects 16kHz input - mismatched sample rates cause feature miscalculations.
    loader_16k = es.MonoLoader(filename=file_path, sampleRate=16000, resampleQuality=4)
    audio_16k = loader_16k()
    loader_44_1k = es.MonoLoader(filename=file_path, sampleRate=44100)
    audio_44_1k = loader_44_1k()

    features = {}

    # Extract file metadata
    audio_file = File(file_path)
    tags = {"path": os.path.abspath(file_path)}

    # Common tag fields across formats
    tag_mapping = {
        "artist": ["TPE1", "©ART", "ARTIST"],
        "album": ["TALB", "©alb", "ALBUM"],
        "title": ["TIT2", "©nam", "TITLE"],
        "date": ["TDRC", "©day", "DATE"],
        "genre": ["TCON", "©gen", "GENRE"],
        "rating": ["POPM", "RATING", "RATING WMP", "RATING AMAZON"],
        "musicbrainz_releasetrackid": [
            "UFID:http://musicbrainz.org",
            "MUSICBRAINZ_RELEASETRACKID",
        ],
        "musicbrainz_artistid": ["MUSICBRAINZ_ARTISTID"],
        "musicbrainz_releasegroupid": ["MUSICBRAINZ_RELEASEGROUPID"],
        "musicbrainz_workid": ["MUSICBRAINZ_WORKID"],
    }

    if hasattr(audio_file, "tags"):
        for field, keys in tag_mapping.items():
            for key in keys:
                try:
                    if key in audio_file.tags:
                        value = audio_file.tags[key]
                        if isinstance(value, list):
                            value = value[0]
                        # Handle special field types
                        if field == "genre":
                            tags[field] = [
                                g.strip() for g in str(value).split(";") if g.strip()
                            ]
                        elif field == "rating":
                            # Normalize rating values from different formats
                            try:
                                rating_val = float(value)
                                if 0 <= rating_val <= 1:
                                    tags[field] = rating_val
                                elif 1 < rating_val <= 5:
                                    tags[field] = rating_val / 5
                                elif rating_val > 5:
                                    tags[field] = min(rating_val / 255, 1.0)
                            except (ValueError, TypeError):
                                tags[field] = 0.0
                        else:
                            # Handle MusicBrainz ReleaseTrackID UFID format
                            if field == "musicbrainz_releasetrackid" and hasattr(
                                value, "data"
                            ):
                                # Extract binary data and decode, removing null bytes
                                tags[field] = value.data.decode(
                                    "utf-8", errors="replace"
                                ).strip("\x00")
                            else:
                                tags[field] = str(value)
                        break
                except ValueError:
                    # Skip invalid tag keys for this file format
                    continue

    # Get duration from audio properties as fallback
    tags["duration"] = len(audio_44_1k) / 44100
    tags["audio_length"] = len(audio_44_1k)

    # Try to get more precise duration from file metadata if available
    if hasattr(audio_file, "info") and hasattr(audio_file.info, "length"):
        tags["duration"] = audio_file.info.length

    features["metadata"] = tags

    # ======================
    # 1. Basic Features
    # ======================
    features["bpm"], beats, _, _, beats_confidence = es.RhythmExtractor2013()(
        audio_44_1k
    )
    features["loudness"] = es.Loudness()(audio_44_1k)
    features["dynamic_complexity"], _ = es.DynamicComplexity()(audio_44_1k)

    # ======================
    # 2. Temporal Dynamics
    # ======================
    frame_size = 1024
    hop_size = 512
    energy = []
    for frame in es.FrameGenerator(audio_44_1k, frameSize=frame_size, hopSize=hop_size):
        spectrum = es.Spectrum()(frame)
        energy.append(np.sum(spectrum**2))

    features["energy_curve"] = {
        "mean": float(np.mean(energy)),
        "std": float(np.std(energy)),
        "peak_count": int(np.sum(np.diff(np.sign(np.diff(energy))) < 0)),
    }

    # ======================
    # 3. Harmonic Content
    # ======================
    # Key detection
    key, scale, key_strength = es.KeyExtractor()(audio_44_1k)
    features["key"] = {"tonic": key, "scale": scale, "confidence": float(key_strength)}

    # Chroma feature extraction with proper framing
    frame_size = 32768
    hop_size = 16384
    chroma_vectors = []

    try:
        chroma_frames = []
        for frame in es.FrameGenerator(
            audio_44_1k, frameSize=frame_size, hopSize=hop_size, startFromZero=True
        ):
            chroma = es.Chromagram()(frame)
            chroma_frames.append(chroma.tolist())

        if chroma_frames:
            # Convert to correct format for ChordsDetection
            chroma_series = chroma_frames
            chords, chords_confidence = es.ChordsDetection()(chroma_series)
            features["chord_stability"] = {
                "unique_chords": len(set(chords)),
                "change_rate": len(chords) / (len(audio_44_1k) / 44100),
            }
        else:
            features["chord_stability"] = "insufficient_data"

    except Exception as e:
        print(f"Chromagram error: {str(e)}")
        features["chord_stability"] = "analysis_failed"

    # ======================
    # 4. Vocal Characteristics (Revised)
    # ======================
    # Using pitch detection as proxy for vocal presence
    frame_size = 2048
    hop_size = 1024
    pitch_detector = es.PredominantPitchMelodia(frameSize=frame_size, hopSize=hop_size)

    pitch_values, _ = pitch_detector(audio_44_1k)
    vocal_features = [1 if p > 0 else 0 for p in pitch_values]

    features["vocal"] = {
        "pitch_presence_ratio": float(np.mean(vocal_features)),
        "pitch_segment_count": int(np.sum(np.diff(vocal_features) > 0)),
        "avg_pitch_duration": float(
            np.mean(np.diff(np.where(vocal_features)[0])) * hop_size / 44100
        ),
    }

    # ======================
    # 5. Timbral Texture
    # ======================
    frame_size = 2048
    hop_size = 1024
    spectra = []

    for frame in es.FrameGenerator(audio_44_1k, frameSize=frame_size, hopSize=hop_size):
        windowed = es.Windowing(type="hann")(frame)
        spectrum = es.Spectrum()(windowed)
        spectra.append(spectrum)

    # Compute spectral contrast on all spectra
    sc = es.SpectralContrast(frameSize=frame_size, numberBands=6)
    contrasts = []
    valleys = []
    for spectrum in spectra:
        contrast, valley = sc(spectrum)
        contrasts.append(contrast)
        valleys.append(valley)

    features["spectral_character"] = {
        "contrast_mean": float(np.mean(contrasts)),
        "brightness": float(np.mean([c[-1] for c in contrasts])),
        "valley_std": float(np.std(valleys)),
    }

    # MFCC analysis
    mfccs = []
    for spectrum in spectra:
        mfcc = es.MFCC(numberCoefficients=13)(spectrum)
        mfccs.append(mfcc[1])

    mfccs = np.array(mfccs)
    features["mfcc"] = {
        "mean": np.mean(mfccs, axis=0).tolist(),
        "covariance": np.cov(mfccs, rowvar=False).tolist(),
        "temporal_variation": float(np.mean(np.std(mfccs, axis=0))),
    }

    # ======================
    # 6. Advanced Rhythm
    # ======================
    if len(beats) > 1:
        ibi = np.diff(beats)
        tempo_variation = np.std(60 / ibi)
        # Syncopation as irregularity of beat intervals
        syncopation = np.mean(np.abs(ibi - np.mean(ibi)))
    else:
        tempo_variation = 0.0
        syncopation = 0.0

    # Danceability estimation
    danceability, dnc_beats = es.Danceability()(audio_44_1k)
    features["groove"] = {
        "tempo_stability": float(1 - tempo_variation / features["bpm"]),
        "beat_confidence": float(np.mean(beats_confidence)),
        "syncopation": float(syncopation),
        "danceability": float(danceability),
        "dnc_bpm": (
            float(np.mean(60 / np.diff(dnc_beats))) if len(dnc_beats) > 1 else 0.0
        ),
        "beat_consistency": (
            float(
                np.corrcoef(
                    beats[: min(len(beats), len(dnc_beats)) - 1],
                    dnc_beats[: min(len(beats), len(dnc_beats)) - 1],
                )[0, 1]
            )
            if len(beats) > 2 and len(dnc_beats) > 2
            else 0.0
        ),
    }

    # ======================
    # 7. Mood Predictions
    # ======================
    mood_model = es.TensorflowPredictMusiCNN(
        graphFilename=files("boldaric.models").joinpath("msd-musicnn-1.pb"),
        output="model/dense/BiasAdd",
    )
    mood_output = mood_model(audio_16k)

    mood_logits = {
        "aggressive": float(mood_output[0, 0]),
        "happy": float(mood_output[0, 1]),
        "party": float(mood_output[0, 2]),
        "relaxed": float(mood_output[0, 3]),
        "sad": float(mood_output[0, 4]),
    }

    features["mood"] = {
        "logits": mood_logits,
        "probabilities": {k: float(sigmoid(v)) for k, v in mood_logits.items()},
    }

    # ======================
    # 8. Genre Predictions
    # ======================
    genre_model = es.TensorflowPredictEffnetDiscogs(
        graphFilename=files("boldaric.models").joinpath("discogs-effnet-bs64-1.pb"),
        output="PartitionedCall:1",
    )
    embeddings = genre_model(audio_16k)
    # Handle 3D output (batch, time, features) by averaging across all dimensions except last
    if embeddings.ndim == 3:
        embeddings = np.mean(embeddings, axis=(0, 1))
    else:
        embeddings = np.mean(embeddings, axis=0)
    # Ensure final 1D array of exactly 128 elements
    features["genre_embeddings"] = embeddings.flatten()[:128].tolist()

    classifier = es.TensorflowPredict2D(
        graphFilename=files("boldaric.models").joinpath(
            "genre_discogs400-discogs-effnet-1.pb"
        ),
        input="serving_default_model_Placeholder",
        output="PartitionedCall:0",
    )
    # Reshape embeddings to 2D array with batch dimension
    classifier_input = np.expand_dims(embeddings, axis=0)
    predictions = classifier(classifier_input)
    scores = np.mean(predictions, axis=0).squeeze().tolist()

    features["genre"] = [
        {"label": label, "score": float(score)}
        for label, score in sorted(zip(labels.labels, scores), key=lambda x: -x[1])[:10]
    ]

    return features
