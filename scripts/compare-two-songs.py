#!/usr/bin/env python3
#
# Compare two songs and look at which dimensions are
#  the most similar

import os
import argparse

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import rich.table
import rich.console

import boldaric
import boldaric.labels

#all_labels = boldaric.labels.labels + \

all_labels = \
    [f'genre {x+1}' for x in range(128)] + \
    [f'mfcc {x+1}' for x in range(13)] + \
    [
        'bpm',
        'loudness',
        'dynamic_complexity',
        'energy_curve_mean',
        'energy_curve_std',
        'energy_curve_peak_count',
        'chord_unique_chords',
        'chord_change_rate',
        'vocal_pitch_presence_ratio',
        'vocal_pitch_segment_count',
        'vocal_avg_pitch_duration',
        'groove_danceability',
        'groove_syncopation',
        'groove_tempo_stability',
        'mood_aggressiveness',
        'mood_happiness',
        'mood_partiness',
        'mood_relaxedness',
        'mood_sadness',
        'spectral_character_brightness',
        'spectral_character_contrast_mean',
        'spectral_character_valley_std'
    ]

def print_results(result_list):
    similarity = [x['similarity_score'] for x in result_list]
    print('Similarity', similarity)

    table = rich.table.Table()
    table.add_column('dimension')

    for i in range(len(result_list)):
        table.add_column(f'contribution {i+1}')
    for i in range(len(result_list)):
        table.add_column(f'difference {i+1}')

    z = zip(all_labels,
            zip(*[x['dimension_contributions'] for x in result_list]),
            zip(*[x['differences'] for x in result_list])
            )

    mins_cont = [min(r['dimension_contributions']) for r in result_list]
    maxs_cont = [max(r['dimension_contributions']) for r in result_list]
    mins_diff = [min(r['differences']) for r in result_list]
    maxs_diff = [max(r['differences']) for r in result_list]

    for label, conts, diffs in z:
        row = [label]

        for i, c in enumerate(conts):
            c0 = make_color_cont(c, mins_cont[i], maxs_cont[i])
            row.append(c0)
        for i, d in enumerate(diffs):
            c0 = make_color_diff(d, mins_diff[i], maxs_diff[i])
            row.append(c0)

        #print(row)
        table.add_row(*row)

    console = rich.console.Console()
    console.print(table)

def make_color_cont(v, min_v, max_v):
    forty = max_v * 0.4

    if v > forty:
        return f'[bold green]{v}'
    elif v < 0:
        return f'[bold red]{v}'
    else:
        return f'{v}'

def make_color_diff(v, min_v, max_v):
    epsilon1 = 1e-3
    epsilon2 = 1e-1

    if v <= epsilon1:
        return f'[bold green]{v}'
    elif v > epsilon2:
        return f'[bold red]{v}'
    else:
        return f'{v}'
    
def compute_cosine_similarity_explanation(query_embedding, result_embedding):
    """
    Compute cosine similarity and per-dimension contributions
    
    Returns:
      similarity_score: overall cosine similarity
      dimension_contributions: contribution of each dimension to the similarity
    """
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
        "result_normalized": r_norm.tolist()
    }


def main(db, song1_id, song2_id):
    song1 = db.get_track_by_subsonic_id(song1_id)
    song2 = db.get_track_by_subsonic_id(song2_id)

    results1 = compute_cosine_similarity_explanation(
        boldaric.feature_helper.track_to_embeddings(song1),
        boldaric.feature_helper.track_to_embeddings(song2)
    )
    results2 = compute_cosine_similarity_explanation(
        boldaric.feature_helper.track_to_embeddings_default_normalization(song1),
        boldaric.feature_helper.track_to_embeddings_default_normalization(song2)
    )
    results3 = compute_cosine_similarity_explanation(
        boldaric.feature_helper.track_to_embeddings_old_normalization(song1),
        boldaric.feature_helper.track_to_embeddings_old_normalization(song2)
    )

    print_results([results1, results2, results3])
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Similarity Analyzer")
    parser.add_argument(
        "-d",
        "--db-path",
        default="./db",
        dest="db_path",
        help="Path to the station database",
    )
    parser.add_argument(
        "song1",
        help = "ID of song1"
    )
    parser.add_argument(
        "song2",
        help = "ID of song2"
    )

    args = parser.parse_args()

    db_name = os.path.join(args.db_path, "stations.db")
    stationdb = boldaric.StationDB(db_name)
    
    main(stationdb, args.song1, args.song2)
    
