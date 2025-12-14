#!/usr/bin/env python3
#
# This script takes a list of similar songs, and songs
#  that might be similar, but shouldn't be included, and
#  evaluates what attributes make them similar, then gives
#  weights.

"""Compute per-dimension scaling factors for a category given:
- positive embeddings (match category)
- negative embeddings (do not match category)

Outputs two weight vectors:
- invvar_weights: based on consistency within positives
- fisher_weights: based on separation between positives and negatives


# Invvar Weights

"Which dimensions are stable inside my category?"

(Positives only)

## Meaning:

If all your mood songs have very similar values in dimension i, that
dimension gets a high weight.

✔ What invvar_weights captures

* Consistency within the positive examples (“Moods songs cluster
  together strongly in dimension 37.”)

* Reliability (“If this dimension has low noise/variance, it’s
  probably important.”)

✘ What it does NOT capture

* Whether negatives have the same value

* Whether this dimension actually distinguishes mood from non-mood

invvar_weights is blind to what non-mood songs look like.

# Fisher Weights

(Positives vs negatives)

This rewards dimensions where:

* Positives have a different mean than negatives (difference in signal)

* Both groups are internally consistent (low variance)

✔ What fisher_weights captures

* Discriminative power (“Mood songs are like this on dimension i;
  non-mood songs are like that.”)

* Importance for classification

* Which dimensions actually encode the category concept

* Pulls in positives × pushes away negatives

✔ Why Fisher is usually better for your use case

Because music embeddings have many dimensions that:

* cluster tightly for your positives

* but also cluster tightly for negatives!

# Conclusion

Which one should you use for your music similarity project?

Use fisher_weights when:

* You want “mood,” “energy,” “explore,” etc. to have real discriminative force

* You want to avoid matching songs that are similar in
  genre/instrumentation/tempo but wrong for the category

* You want weighted similarity to feel meaningful and “category-aware”

Use invvar_weights when:

* You only have positives (no reliable negatives)

* You want to understand structure inside the category first

* You want to visualize category cohesion

## My Thoughts:

For energy and/or mood, I think it is ok to jump genres, so invvar may be more
useful for that category.

"""

import argparse
import numpy as np
import yaml
import os

import boldaric



# -----------------------------
# Weight computation functions
# -----------------------------

def compute_inverse_variance_weights(
    X_pos: np.ndarray,
    eps: float = 1e-6,
    alpha: float = 1.0,
) -> np.ndarray:
    """
    Weights ~ 1 / std(pos) per dimension.
    - Low variance across positives -> higher weight.
    - alpha > 1.0 makes the effect stronger, < 1.0 makes it softer.
    """
    X_pos = np.asarray(X_pos, dtype=np.float32)
    std_pos = X_pos.std(axis=0)  # shape (D,)

    w = 1.0 / (std_pos + eps)
    # Optional sharpening/softening
    if alpha != 1.0:
        w = w ** alpha

    # Normalize so max weight = 1.0 (for sanity)
    w /= (w.max() + eps)
    return w


def compute_fisher_discriminative_weights(
    X_pos: np.ndarray,
    X_neg: np.ndarray,
    eps: float = 1e-6,
    alpha: float = 1.0,
) -> np.ndarray:
    """
    Fisher-style per-dimension weights:

        w_i ~ (mu_pos[i] - mu_neg[i])^2 / (var_pos[i] + var_neg[i])

    - Large when positives & negatives are far apart but each group
      is internally consistent.
    - alpha > 1.0 amplifies contrast, < 1.0 softens it.
    """
    X_pos = np.asarray(X_pos, dtype=np.float32)
    X_neg = np.asarray(X_neg, dtype=np.float32)

    mu_pos = X_pos.mean(axis=0)
    mu_neg = X_neg.mean(axis=0)

    var_pos = X_pos.var(axis=0)
    var_neg = X_neg.var(axis=0)

    num = (mu_pos - mu_neg) ** 2
    den = var_pos + var_neg + eps

    w = num / den  # shape (D,)

    if alpha != 1.0:
        w = w ** alpha

    # Normalize so max weight = 1.0
    w /= (w.max() + eps)
    return w


# -----------------------------
# Example: weighted cosine
# -----------------------------

def weighted_cosine(q: np.ndarray, x: np.ndarray, w: np.ndarray) -> float:
    """
    Compute cosine similarity after per-dimension scaling by w.
    """
    q = np.asarray(q, dtype=np.float32)
    x = np.asarray(x, dtype=np.float32)
    w = np.asarray(w, dtype=np.float32)

    q_w = q * w
    x_w = x * w

    denom = (np.linalg.norm(q_w) * np.linalg.norm(x_w))
    if denom == 0.0:
        return 0.0
    return float(np.dot(q_w, x_w) / denom)


def load_embeddings(db, inp):
    with open(inp, 'r') as f:
        song_ids = yaml.safe_load(f)['tracks']
        tracks = [db.get_track_by_subsonic_id(x) for x in song_ids]
        assert None not in tracks, f"Invalid subsonic_id in {inp}"
        return np.array([boldaric.feature_helper.track_to_embeddings(t) for t in tracks])

# -----------------------------
# Main script / demo
# -----------------------------

def main(db, similar, different):
    X_pos = load_embeddings(db, similar)
    X_neg = load_embeddings(db, different)

    print(f"Loaded positives: {X_pos.shape}, negatives: {X_neg.shape}")

    # Compute weights
    invvar_weights = compute_inverse_variance_weights(X_pos, eps=1e-6, alpha=1.0)
    fisher_weights = compute_fisher_discriminative_weights(
        X_pos, X_neg, eps=1e-6, alpha=1.0
    )

    # Save them for use in your Chroma reranking code
    #save_weights("mood_invvar_weights.npy", invvar_weights)
    #save_weights("mood_fisher_weights.npy", fisher_weights)
    print("#### Invvar Weights ####")
    print(invvar_weights.tolist())
    print("")
    print("#### Fisher Weights ####")
    print(fisher_weights.tolist())
    print("")

    # # Quick demo: compare similarity for one random query
    # q = X_pos[0]  # treat one positive as a query
    # x_similar = X_pos[1]
    # x_dissimilar = X_neg[0]

    # base_cos_sim_similar = np.dot(q, x_similar) / (
    #     np.linalg.norm(q) * np.linalg.norm(x_similar)
    # )
    # base_cos_sim_dissim = np.dot(q, x_dissimilar) / (
    #     np.linalg.norm(q) * np.linalg.norm(x_dissimilar)
    # )

    # w = fisher_weights  # pick whichever weights you like

    # w_cos_sim_similar = weighted_cosine(q, x_similar, w)
    # w_cos_sim_dissim = weighted_cosine(q, x_dissimilar, w)

    # print("\nBase cosine similarity (no weights):")
    # print(f"  similar   = {base_cos_sim_similar:.4f}")
    # print(f"  dissimilar= {base_cos_sim_dissim:.4f}")

    # print("\nWeighted cosine similarity (with Fisher weights):")
    # print(f"  similar   = {w_cos_sim_similar:.4f}")
    # print(f"  dissimilar= {w_cos_sim_dissim:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Similarity Analyzer")
    parser.add_argument(
        "-d",
        "--db-path",
        default="./db",
        dest="db_path",
        help="Path to the station database",
    )
    parser.add_argument(
        "similar",
        help = "JSON list of subsonic_ids for songs that are similar"
    )
    parser.add_argument(
        "different",
        help = "JSON list of subsonic_ids for songs that are different. These should be in the same range as the songs in similar, but songs you want to exclude"
    )

    args = parser.parse_args()

    db_name = os.path.join(args.db_path, "stations.db")
    stationdb = boldaric.StationDB(db_name)
    
    main(stationdb, args.similar, args.different)
