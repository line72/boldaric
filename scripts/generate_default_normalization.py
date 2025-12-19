#!/usr/bin/env python3
#
# Scan through a set of song embeddings and calculate
#  normalization values for each dimesions. The algorithm will
#  slightly change based upon the model that generated those
#  embeddings.
#
# These will then be hard-coded as used as the "default" normalization
#  for all new songs

import argparse
import os
import numpy as np

import boldaric

def main(db):
    with db.Session() as session:
        query = session.query(boldaric.models.Track).yield_per(1000)

        embeddings = []
        for track in query:
            embeddings.append(boldaric.feature_helper.DefaultFeatureHelper.track_to_embeddings(track))

        embeddings = np.array(embeddings, dtype=np.float32)
            
        # Genre is first 128D
        # These uses l2 normalization PER track, not across the
        #  whole dataset. Skip
        #genre_embeddings = embeddings[:, :128]

        # End normalizations
        # This will be a list of 2D tuples (mu,sigma)
        normalizations = []
        
        # MFCC is the next 13D
        # Calculate normalization across the whole
        #  data set
        mfcc_embeddings = embeddings[:, 128:128+13]
        print(mfcc_embeddings.shape)
        mfcc_mu = mfcc_embeddings.mean(axis=0)
        mfcc_sigma = mfcc_embeddings.std(axis=0)
        # We'll save these values, and freeze them, then
        #  apply them to each track using:
        # mfcc_norm = (mfcc_track - mfcc_mu) / mfcc_sigma

        # For mfcc_mu and mfcc_sigma, each will be a 13D
        #  array. I then zip them up, so I get 2D tuples
        normalizations.extend(list(zip(mfcc_mu, mfcc_sigma)))

        # Everything else is 1D and should be normalized across
        # the whole dataset using z-score
        # Note, a few of these are log1p + z-score, noted by index
        rest = embeddings[:, 128+13:]

        # apply log1p to
        #  bpm: dim 141
        #  unique_chords: dim 147
        #  vocal_avg_pitch_duration: dim 151
        bpm_idx = 141 - (128+13)
        unique_chords_idx = 147 - (128+13)
        vocal_avg_pitch_duration_idx = 151 - (128+13)

        rest[:, bpm_idx] = np.log1p(rest[:, bpm_idx])
        rest[:, unique_chords_idx] = np.log1p(rest[:, unique_chords_idx])
        rest[:, vocal_avg_pitch_duration_idx] = np.log1p(rest[:, vocal_avg_pitch_duration_idx])
        
        mus = rest.mean(axis=0)
        sigmas = rest.std(axis=0)
        normalizations.extend(list(zip(mus, sigmas)))

        print(len(normalizations))
        print(normalizations)
        
                              

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Similarity Analyzer")
    parser.add_argument(
        "-d",
        "--db-path",
        default="./db",
        dest="db_path",
        help="Path to the station database",
    )

    args = parser.parse_args()

    db_name = os.path.join(args.db_path, "stations.db")
    stationdb = boldaric.StationDB(db_name)
    
    main(stationdb)
    
