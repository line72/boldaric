#!/usr/bin/env python3
#
# Compare two songs and look at which dimensions are
#  the most similar

import os
import argparse

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

def print_results(song1, song2, result_list):
    print(f'Comparing {song1.artist} - {song1.title} vs {song2.artist} - {song2.title}')
    
    similarity = [f"{x['name']}={x['similarity_score']}" for x in result_list]
    print('Similarity', similarity)

    table = rich.table.Table()
    table.add_column('dimension')

    for i in result_list:
        table.add_column(f'Contribution {i["name"]}')
    for i in result_list:
        table.add_column(f'Difference {i["name"]}')

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
        return f'[bold green]{v:.6f}'
    elif v < 0:
        return f'[bold red]{v:.6f}'
    else:
        return f'{v:.6f}'

def make_color_diff(v, min_v, max_v):
    epsilon1 = 1e-3
    epsilon2 = 1e-1

    if v <= epsilon1:
        return f'[bold green]{v:.6f}'
    elif v > epsilon2:
        return f'[bold red]{v:.6f}'
    else:
        return f'{v:.6f}'
    
def compute_cosine_similarity_explanation(name, query_embedding, result_embedding):
    results = boldaric.utils.compute_cosine_similarity_explanation(
        query_embedding, result_embedding)

    results['name'] = name

    return results

def compute_l2_similarity_explanation(name, query_embedding, result_embedding):
    results = boldaric.utils.compute_l2_similarity_explanation(
        query_embedding, result_embedding)

    results['name'] = name

    return results

def compute_ip_similarity_explanation(name, query_embedding, result_embedding):
    results = boldaric.utils.compute_ip_similarity_explanation(
        query_embedding, result_embedding)

    results['name'] = name

    return results

def main(db, song1_id, song2_id):
    song1 = db.get_track_by_subsonic_id(song1_id)
    song2 = db.get_track_by_subsonic_id(song2_id)

    MODULE = boldaric.feature_helper.GenreFeatureHelper
    
    cosine = compute_cosine_similarity_explanation('Cosine',
        MODULE.track_to_embeddings(song1),
        MODULE.track_to_embeddings(song2)
    )
    
    l2 = compute_l2_similarity_explanation('L2',
        MODULE.track_to_embeddings(song1),
        MODULE.track_to_embeddings(song2)
    )
    
    ip = compute_ip_similarity_explanation('IP',
        MODULE.track_to_embeddings(song1),
        MODULE.track_to_embeddings(song2)
    )
    
    # results2 = compute_cosine_similarity_explanation('Default',
    #     boldaric.feature_helper.DefaultFeatureHelper.track_to_embeddings(song1),
    #     boldaric.feature_helper.DefaultFeatureHelper.track_to_embeddings(song2)
    # )
    # results3 = compute_cosine_similarity_explanation('Mood',
    #     boldaric.feature_helper.MoodFeatureHelper.track_to_embeddings(song1),
    #     boldaric.feature_helper.MoodFeatureHelper.track_to_embeddings(song2)
    # )
    # results4 = compute_cosine_similarity_explanation('Genre',
    #     boldaric.feature_helper.GenreFeatureHelper.track_to_embeddings(song1),
    #     boldaric.feature_helper.GenreFeatureHelper.track_to_embeddings(song2)
    # )

    #print_results(song1, song2, [results1, results2, results3, results4])
    print_results(song1, song2, [cosine, l2, ip])
    

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
    
