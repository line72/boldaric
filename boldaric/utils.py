# Copyright (c) 2025 Marcus Dillavou <line72@line72.net>
# Part of the Boldaric Project:
#  https://github.com/line72/boldaric
# Released under the AGPLv3 or later

import logging


def get_logger():
    return logging.getLogger("boldaric")


def compute_cosine_similarity_explanation(query_embedding, result_embedding):
    """
    Compute cosine similarity and per-dimension contributions

    Returns:
      similarity_score: overall cosine similarity
      dimension_contributions: contribution of each dimension to the similarity
    """
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np

    # Convert to numpy arrays
    q = np.array(query_embedding)
    r = np.array(result_embedding)

    # Normalize the vectors
    q_norm = q / np.linalg.norm(q)
    r_norm = r / np.linalg.norm(r)

    # Overall cosine similarity
    similarity_score = np.dot(q_norm, r_norm)

    # Per-dimension contribution to dot product (before normalization)
    # This shows how each dimension contributes to the similarity
    dimension_contributions = q_norm * r_norm

    # Alternative: contribution based on raw difference
    # This shows which dimensions differ the most
    differences = np.abs(q_norm - r_norm)

    return {
        "similarity_score": similarity_score,
        "dimension_contributions": dimension_contributions.tolist(),
        "differences": differences.tolist(),
        "query_normalized": q_norm.tolist(),
        "result_normalized": r_norm.tolist(),
    }


def compute_l2_similarity_explanation(query_embedding, result_embedding):
    """
    Compute L2 distance and per-dimension contributions
    
    Returns:
      similarity_score: similarity score derived from L2 distance (1 / (1 + distance))
      distance: overall L2 distance
      dimension_contributions: contribution of each dimension to the distance
    """
    import numpy as np

    # Convert to numpy arrays
    q = np.array(query_embedding)
    r = np.array(result_embedding)

    # Overall L2 distance (Euclidean distance)
    distance = np.linalg.norm(q - r)
    
    # Convert distance to similarity score (1 / (1 + distance))
    # This ensures that:
    # - distance=0 -> similarity=1 (most similar)
    # - distance=inf -> similarity=0 (least similar)
    # - values are in range (0, 1]
    similarity_score = 1.0 / (1.0 + distance)

    # Per-dimension contribution to squared difference
    # This shows how much each dimension contributes to the total distance
    squared_differences = (q - r) ** 2
    dimension_contributions = squared_differences

    # Raw differences (signed)
    differences = q - r

    return {
        "similarity_score": similarity_score,
        "distance": distance,
        "dimension_contributions": dimension_contributions.tolist(),
        "differences": differences.tolist(),
        "query": q.tolist(),
        "result": r.tolist(),
    }


def compute_ip_similarity_explanation(query_embedding, result_embedding):
    """
    Compute inner product similarity and per-dimension contributions
    
    Returns:
      similarity_score: overall inner product
      dimension_contributions: contribution of each dimension to the similarity
    """
    import numpy as np

    # Convert to numpy arrays
    q = np.array(query_embedding)
    r = np.array(result_embedding)

    # Overall inner product
    similarity_score = np.dot(q, r)

    # Per-dimension contribution to the dot product
    # This shows how each dimension contributes to the similarity
    dimension_contributions = q * r

    # Absolute differences
    differences = np.abs(q - r)

    return {
        "similarity_score": similarity_score,
        "dimension_contributions": dimension_contributions.tolist(),
        "differences": differences.tolist(),
        "query": q.tolist(),
        "result": r.tolist(),
    }
