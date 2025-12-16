#!/usr/bin/env python3
#
# This script runs through all the tracks in the sqlitedb
# and stuffs the embeddings with our normalization into
#  the vectordb.

import argparse
import os

from sqlalchemy import func
import rich.progress

import boldaric

def go(stationdb, vectordb):
    with rich.progress.Progress(
            rich.progress.SpinnerColumn(),
            rich.progress.TextColumn("[progress.description]{task.description:.20s}"),
            rich.progress.BarColumn(),
            rich.progress.MofNCompleteColumn(),
            rich.progress.TimeRemainingColumn(),
            rich.progress.TimeElapsedColumn(),
            expand=True,
    ) as progress:
        with stationdb.Session() as session:
            total_count = session.query(func.count(boldaric.models.Track.id)).scalar()
            query = session.query(boldaric.models.Track).yield_per(1000)

            # Delete the whole collection
            vectordb.delete_and_recreate_collections()
            
            task_id = progress.add_task('Re-Indexing', total=total_count)
                    
            for track in query:
                try:
                    vectordb.add_track(track.subsonic_id, track)
                except Exception as e:
                    import traceback
                    print(f'Error inserting track {track.subsonic_id}: {e}')
                    print(traceback.format_exc())
                progress.update(task_id, advance=1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = 'Reset vector db')
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
    vectordb = boldaric.VectorDB.build_from_http()

    
    go(stationdb, vectordb)
