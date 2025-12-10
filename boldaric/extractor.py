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
import ast

import numpy as np
from mutagen import File
from mutagen.id3 import TRCK

from importlib.resources import files

from . import labels


def extract_features(file_path):
    """Extract features from an audio file."""
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

    # Extract metadata
    audio_file = File(file_path)
    features["metadata"] = extract_metadata(file_path, audio_file, audio_44_1k)

    # Extract basic features
    bpm, beats, beats_confidence, loudness, dynamic_complexity = extract_basic_features(
        audio_44_1k
    )
    features["bpm"] = bpm
    features["loudness"] = loudness
    features["dynamic_complexity"] = dynamic_complexity

    # Extract temporal dynamics
    features["energy_curve"] = extract_temporal_dynamics(audio_44_1k)

    # Extract harmonic content
    key_features, chord_stability = extract_harmonic_content(audio_44_1k)
    features["key"] = key_features
    features["chord_stability"] = chord_stability

    # Extract vocal characteristics
    features["vocal"] = extract_vocal_characteristics(audio_44_1k)

    # Extract timbral texture
    features["mfcc"], features["spectral_character"] = extract_timbral_texture(
        audio_44_1k
    )

    # Extract advanced rhythm features
    features["groove"] = extract_advanced_rhythm(
        audio_44_1k, bpm, beats, beats_confidence
    )

    # Extract mood predictions
    features["mood"] = extract_mood_predictions(audio_16k)

    # Extract genre predictions
    genre, genre_embeddings = extract_genre_predictions(audio_16k)
    features["genre"] = genre
    features["genre_embeddings"] = genre_embeddings

    return features


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def extract_metadata(file_path, audio_file=None, audio_44_1k=None):
    """Extract metadata from audio file."""
    if audio_file is None:
        audio_file = File(file_path)
    if audio_44_1k is None:
        import essentia

        # disable logging in all the dumb possible ways
        essentia.log.infoActive = False
        essentia.log.warningActive = False

        import essentia.standard as es

        loader_44_1k = es.MonoLoader(filename=file_path, sampleRate=44100)
        audio_44_1k = loader_44_1k()

    tags = {
        "path": os.path.abspath(file_path),
        "artist": "",
        "album": "",
        "title": "",
        "date": "",
        "genre": [],
        "rating": 0.0,
        "musicbrainz_releasetrackid": "",
        "musicbrainz_artistid": "",
        "musicbrainz_releasegroupid": "",
        "musicbrainz_workid": "",
        "tracknumber": 0,
        "releasetype": "album",
        "releasestatus": "official",
        "duration": 0,
        "audio_length": 0,
    }

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
            "TXXX:MUSICBRAINZ_RELEASETRACKID",
            "MUSICBRAINZ_RELEASETRACKID",
        ],
        "musicbrainz_artistid": ["TXXX:MUSICBRAINZ_ARTISTID", "MUSICBRAINZ_ARTISTID"],
        "musicbrainz_releasegroupid": [
            "TXXX:MUSICBRAINZ_RELEASEGROUPID",
            "MUSICBRAINZ_RELEASEGROUPID",
        ],
        "musicbrainz_workid": ["TXXX:MUSICBRAINZ_WORKID", "MUSICBRAINZ_WORKID"],
        "tracknumber": ["TRCK", "trkn", "TRACKNUMBER", "TXXX:TRACKNUMBER"],
        "releasetype": [
            "MusicBrainz Album Type",
            "TXXX:RELEASETYPE",
            "RELEASETYPE",
            "TXXX:MUSICBRAINZ_ALBUMTYPE",
            "MUSICBRAINZ_ALBUMTYPE",
        ],
        "releasestatus": ["TXXX:RELEASESTATUS", "RELEASESTATUS"],
    }

    def convert_to_string(value):
        if isinstance(value, (bytes, bytearray)):
            # Handle binary data directly
            return value.decode("utf-8", errors="replace").strip("\x00")

        # It appears some tagging software literally encodes a string
        # as "b'hello'" -- which indicates whatever tagger this was
        # incorrectly did a byte -> str conversion. This is a lame
        # attempt at fixing this bullshit
        if isinstance(value, str) and value.startswith("b'"):
            try:
                return ast.literal_eval(value).decode("utf-8")
            except ValueError:
                pass

        return str(value)

    if hasattr(audio_file, "tags"):
        for field, keys in tag_mapping.items():
            for key in keys:
                try:
                    if key in audio_file.tags:
                        value = audio_file.tags[key]
                        # Handle special field types
                        if field == "genre":
                            if isinstance(value, list):
                                tags[field] = [convert_to_string(x) for x in value]
                            else:
                                tags[field] = [
                                    g.strip()
                                    for g in convert_to_string(value).split(";")
                                    if g.strip()
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
                        elif field == "tracknumber":
                            # Handle track number parsing
                            try:
                                if isinstance(value, list):
                                    value = value[0]

                                # Handle formats like "1/10" or just "1"
                                if isinstance(value, TRCK):
                                    tags[field] = int(value.text[0])
                                elif isinstance(value, int):
                                    tags[field] = value
                                elif isinstance(value, str) and "/" in value:
                                    track_num = value.split("/")[0]
                                    tags[field] = int(track_num)
                                else:
                                    tags[field] = int(value)
                            except (ValueError, TypeError):
                                tags[field] = 0
                        elif field == "musicbrainz_releasetrackid" and hasattr(
                            value, "data"
                        ):
                            # Handle MusicBrainz ReleaseTrackID UFID format
                            # Extract binary data and decode, removing null bytes
                            tags[field] = convert_to_string(value.data)
                        else:
                            # Properly handle binary data by checking type first
                            if isinstance(value, list):
                                tags[field] = "/".join(
                                    [convert_to_string(x) for x in value]
                                )
                            else:
                                tags[field] = convert_to_string(value)
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

    return tags


def extract_basic_features(audio_44_1k):
    """Extract basic audio features including BPM, loudness, and dynamic complexity."""
    import essentia.standard as es

    bpm, beats, _, _, beats_confidence = es.RhythmExtractor2013()(audio_44_1k)
    loudness = es.Loudness()(audio_44_1k)
    dynamic_complexity, _ = es.DynamicComplexity()(audio_44_1k)

    return (bpm, beats, beats_confidence, loudness, dynamic_complexity)


def extract_temporal_dynamics(audio_44_1k):
    """Extract temporal dynamics features from audio."""
    import essentia.standard as es

    frame_size = 1024
    hop_size = 512
    energy = []
    for frame in es.FrameGenerator(audio_44_1k, frameSize=frame_size, hopSize=hop_size):
        spectrum = es.Spectrum()(frame)
        energy.append(np.sum(spectrum**2))

    return {
        "mean": float(np.mean(energy)),
        "std": float(np.std(energy)),
        "peak_count": int(np.sum(np.diff(np.sign(np.diff(energy))) < 0)),
    }


def extract_harmonic_content(audio_44_1k):
    """Extract harmonic content features including key and chord stability."""
    import essentia.standard as es

    # Key detection
    key, scale, key_strength = es.KeyExtractor()(audio_44_1k)
    key_features = {"tonic": key, "scale": scale, "confidence": float(key_strength)}

    # Chroma feature extraction with proper framing
    frame_size = 32768
    hop_size = 16384

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
            chord_stability = {
                "unique_chords": len(set(chords)),
                "change_rate": len(chords) / (len(audio_44_1k) / 44100),
            }
        else:
            chord_stability = "insufficient_data"

    except Exception as e:
        print(f"Chromagram error: {str(e)}")
        chord_stability = "analysis_failed"

    return (key_features, chord_stability)


def extract_vocal_characteristics(audio_44_1k):
    """Extract vocal characteristics from audio."""
    import essentia.standard as es

    # Using pitch detection as proxy for vocal presence
    frame_size = 2048
    hop_size = 1024
    pitch_detector = es.PredominantPitchMelodia(frameSize=frame_size, hopSize=hop_size)

    pitch_values, _ = pitch_detector(audio_44_1k)
    vocal_features = [1 if p > 0 else 0 for p in pitch_values]

    return {
        "pitch_presence_ratio": float(np.mean(vocal_features)),
        "pitch_segment_count": int(np.sum(np.diff(vocal_features) > 0)),
        "avg_pitch_duration": float(
            np.mean(np.diff(np.where(vocal_features)[0])) * hop_size / 44100
        ),
    }


def extract_timbral_texture(audio_44_1k):
    """Extract timbral texture features including spectral contrast and MFCC."""
    import essentia.standard as es

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

    spectral_character = {
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
    mfcc_features = {
        "mean": np.mean(mfccs, axis=0).tolist(),
        "covariance": np.cov(mfccs, rowvar=False).tolist(),
        "temporal_variation": float(np.mean(np.std(mfccs, axis=0))),
    }

    return mfcc_features, spectral_character


def extract_advanced_rhythm(audio_44_1k, bpm, beats, beats_confidence):
    """Extract advanced rhythm features."""
    import essentia.standard as es

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

    return {
        "tempo_stability": (float(1 - tempo_variation / bpm) if bpm > 0 else 0.0),
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


def extract_mood_predictions(audio_16k):
    """Extract mood predictions from audio."""
    import essentia.standard as es

    mood_model = es.TensorflowPredictMusiCNN(
        graphFilename=str(files("boldaric.models").joinpath("msd-musicnn-1.pb")),
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

    return {
        "logits": mood_logits,
        "probabilities": {k: float(sigmoid(v)) for k, v in mood_logits.items()},
    }


def extract_genre_predictions(audio_16k):
    """Extract genre predictions from audio."""
    import essentia.standard as es

    genre_model = es.TensorflowPredictEffnetDiscogs(
        graphFilename=str(
            files("boldaric.models").joinpath("discogs-effnet-bs64-1.pb")
        ),
        output="PartitionedCall:1",
    )
    embeddings = genre_model(audio_16k)
    # Handle 3D output (batch, time, features) by averaging across all dimensions except last
    if embeddings.ndim == 3:
        embeddings = np.mean(embeddings, axis=(0, 1))
    else:
        embeddings = np.mean(embeddings, axis=0)
    # Ensure final 1D array of exactly 128 elements
    genre_embeddings = embeddings.flatten()[:128].tolist()

    classifier = es.TensorflowPredict2D(
        graphFilename=str(
            files("boldaric.models").joinpath("genre_discogs400-discogs-effnet-1.pb")
        ),
        input="serving_default_model_Placeholder",
        output="PartitionedCall:0",
    )
    # Reshape embeddings to 2D array with batch dimension
    classifier_input = np.expand_dims(embeddings, axis=0)
    predictions = classifier(classifier_input)
    scores = np.mean(predictions, axis=0).squeeze().tolist()

    return (
        [
            {"label": label, "score": float(score)}
            for label, score in sorted(zip(labels.labels, scores), key=lambda x: -x[1])[
                :10
            ]
        ],
        genre_embeddings,
    )
