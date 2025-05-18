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

def features_to_embeddings(features: dict) -> list[float]:
    """Convert a feature list from metadata or the extractor into
    database embeddings"""
    # Create a combined embedding
    embedding = []

    # 1. Genre Embeddings (128D)
    genre_embeds = np.array(features.get("genre_embeddings", np.zeros(128))).flatten()
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
    mfcc_stats = features.get("mfcc", {})
    mfcc_means = np.array(mfcc_stats.get("mean", np.zeros(13)))[:13]

    # Normalize the entire MFCC vector rather than per-feature
    norm = np.linalg.norm(mfcc_means)
    if norm > 1e-9:
        mfcc_means = mfcc_means / norm

    embedding.extend(mfcc_means.tolist())

    # 3. Groove features (2D)
    groove = features.get("groove", {})
    danceability = max(0, min(1, groove.get("danceability", 0.5)))
    tempo_stability = max(0, min(1, groove.get("tempo_stability", 0.5)))
    embedding.extend([danceability, tempo_stability])

    # 4. Mood features (5D)
    mood_probs = features.get("mood", {}).get("probabilities", {})
    mood_features = [
        mood_probs.get("aggressive", 0.5),
        mood_probs.get("happy", 0.5),
        mood_probs.get("party", 0.5),
        mood_probs.get("relaxed", 0.5),
        mood_probs.get("sad", 0.5),
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


def calculate_similarities(query_embedding, result_embedding, distance):
    "Try to quantify similarities in different dimensions, since we know what our embeddings mean"
    # Calculate feature contributions
    query_genre = query_embedding[:128]
    query_mfcc = query_embedding[128:141]
    query_groove = query_embedding[141:143]
    query_mood = query_embedding[143:]

    result_genre = result_embedding[:128]
    result_mfcc = result_embedding[128:141]
    result_groove = result_embedding[141:143]
    result_mood = result_embedding[143:]

    genre_similarity = cosine_similarity([query_genre], [result_genre])[0][0]
    mfcc_similarity = cosine_similarity([query_mfcc], [result_mfcc])[0][0]
    groove_similarity = cosine_similarity([query_groove], [result_groove])[0][0]
    mood_similarity = cosine_similarity([query_mood], [result_mood])[0][0]

    total_similarity = 1 - distance
    genre_contribution = (
        (genre_similarity * 128 / 148) / total_similarity * 100
        if total_similarity > 0
        else 0
    )
    mfcc_contribution = (
        (mfcc_similarity * 13 / 148) / total_similarity * 100
        if total_similarity > 0
        else 0
    )
    groove_contribution = (
        (groove_similarity * 2 / 148) / total_similarity * 100
        if total_similarity > 0
        else 0
    )
    mood_contribution = (
        (mood_similarity * 5 / 148) / total_similarity * 100
        if total_similarity > 0
        else 0
    )

    return {
        "feature_contributions": {
            "genre": genre_contribution,
            "mfcc": mfcc_contribution,
            "groove": groove_contribution,
            "mood": mood_contribution,
        },
        "component_similarities": {
            "genre": genre_similarity,
            "mfcc": mfcc_similarity,
            "groove": groove_similarity,
            "mood": mood_similarity,
        },
    }


def print_similarities(final_results, n_results):
    for result in final_results[:n_results]:
        print(f"ID: {result['id']}")
        print(f"Similarity: {result['similarity']:.4f}")
        print("Feature Contributions:")
        for feature, contribution in result["feature_contributions"].items():
            print(f"  {feature.capitalize()}: {contribution:.1f}%")
        print("Component Similarities:")
        for component, similarity in result["component_similarities"].items():
            print(f"  {component.capitalize()}: {similarity:.4f}")
        print()
