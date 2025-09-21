# Copyright (c) 2025 Marcus Dillavou <line72@line72.net>
# Part of the Boldaric Project:
#  https://github.com/line72/boldaric
# Released under the AGPLv3 or later

# This is a tool that connects to a subsonic server and iterates
#  through all the songs on the server. For each song, it will check
#  vectordb to see if the track exists by the subsonic_id.
#
# If the file does not exist in the database, it will download the
# file locally, then run the extractor.extract_features on it. The
# results will then be saved to the vectordb. The local file is then
# removed from the cache.
#
# This tool will run concurrently using the multiprocessing library to
# speed up processing.
#
# It will also show a progress bar of the status

import os
import argparse
import random
import tempfile
import unicodedata

import multiprocessing
from queue import Empty

from unidecode import unidecode
import rich.progress

import boldaric
import boldaric.subsonic


def get_artist_from_name(conn, artist_name):
    artist_id = get_artist_id(conn, artist_name)
    return get_artist(conn, artist_id)


def get_artist(conn, artist_id):
    if artist_id:
        response = conn.getArtist(artist_id)
        if "artist" not in response or "album" not in response["artist"]:
            return None
        return response["artist"]
    return None


def get_artist_id(conn, artist_name):
    response = conn.search3(query=artist_name)
    if "searchResult3" in response and "artist" in response["searchResult3"]:
        for artist in response["searchResult3"]["artist"]:
            if artist["name"].lower() == artist_name.lower():
                return artist["id"]
    return None


def get_songs(conn, artist, size=500):
    album_ids = [(album["id"], album["name"]) for album in artist["album"]]
    yield from get_albums(conn, album_ids)


def get_albums(conn, albums_list):
    for album_id, album_name in albums_list:
        album_response = conn.getAlbum(album_id)
        songs = album_response["album"]["song"]
        yield from songs


def song_generator(song_queue, progress_queue, num_workers, artist_names=[]):
    try:
        conn = boldaric.subsonic.make_from_parameters(
            os.getenv("NAVIDROME_URL"),
            os.getenv("NAVIDROME_USERNAME"),
            os.getenv("NAVIDROME_PASSWORD"),
        )

        if artist_names and len(artist_names) > 0:
            for artist_name in artist_names:
                artist = get_artist_from_name(conn, artist_name)
                if artist:
                    num_songs = sum([int(x["songCount"]) for x in artist["album"]])
                    progress_queue.put(("ADD", artist["id"], artist["name"], num_songs))

                    for song in get_songs(conn, artist=artist):
                        song_queue.put(("PROCESS", artist["id"], song))
        else:
            # Start fetching artists in random order
            resp = conn.getArtists()
            artist_ids = []
            for a in resp["artists"]["index"]:
                for a2 in a["artist"]:
                    artist_ids.append(a2["id"])

            # shutffle the artists
            random.shuffle(artist_ids)
            for artist_id in artist_ids:
                artist = get_artist(conn, artist_id)
                if artist:
                    num_songs = sum([int(x["songCount"]) for x in artist["album"]])
                    progress_queue.put(("ADD", artist["id"], artist["name"], num_songs))

                    for song in get_songs(conn, artist=artist):
                        song_queue.put(("PROCESS", artist["id"], song))
    except Exception as e:
        print(f"SubsonicWorker::song_generator: [ERROR] {e}")
    finally:
        # We are done, stop everything
        for _ in range(num_workers):
            song_queue.put(None)  # Signal that there are no more songs for each worker


def process_song(song, conn, db):
    try:
        # Check if song is in vectordb database by subsonic id
        subsonic_id = song["id"]
        if db.track_exists(subsonic_id):
            return {"status": "success", "id": subsonic_id, "path": song["path"]}

        # Download the song to a temporary location
        response = conn.stream(song["id"]).read()
        with tempfile.NamedTemporaryFile(suffix="." + song["suffix"]) as temp_file:
            temp_file.write(response)
            temp_file.flush()

            features = boldaric.extractor.extract_features(temp_file.name)
            db.add_track(subsonic_id, features)

        return {"status": "success", "id": subsonic_id, "path": song["path"]}
    except Exception as e:
        print(f"Exception during song {song}: {e}")
        import traceback

        traceback.print_exc()
        return {
            "status": "error",
            "id": song["id"],
            "path": song["path"],
            "error": str(e),
        }


def worker(song_queue, progress_queue):
    conn = boldaric.subsonic.make_from_parameters(
        os.getenv("NAVIDROME_URL"),
        os.getenv("NAVIDROME_USERNAME"),
        os.getenv("NAVIDROME_PASSWORD"),
    )
    db = boldaric.VectorDB.build_from_http()

    while True:
        q = song_queue.get()
        match q:
            case None:
                return
            case ("PROCESS", artist_id, song):
                result = process_song(song, conn, db)

                # update the progress
                progress_queue.put(("UPDATE", artist_id, 1))

                if result["status"] == "error":
                    print(f"Error processing {result['path']}: {result['error']}")
            case _:
                print(f"worker got unknown message {q}")


def latinize_text(text):
    # Convert to latin
    return unidecode(text)


def progress_bar_worker(progress_queue, stop_queue):
    in_progress = {}
    completed = []

    with rich.progress.Progress(
        rich.progress.SpinnerColumn(),
        rich.progress.TextColumn("[progress.description]{task.description:.20s}"),
        rich.progress.BarColumn(),
        rich.progress.MofNCompleteColumn(),
        rich.progress.TimeRemainingColumn(),
        rich.progress.TimeElapsedColumn(),
        expand=True,
    ) as progress:
        while True:
            try:
                q = progress_queue.get(timeout=0.1)
                match q:
                    case ("ADD", artist_id, artist_name, total_songs):
                        # We have an actual update, so now create a progress bar
                        task_id = progress.add_task(
                            latinize_text(artist_name),
                            total=total_songs,
                        )
                        progress.update(task_id, advance=0)

                        # move to inprogress
                        in_progress[artist_id] = {
                            "task_id": task_id,
                            "artist_name": artist_name,
                            "total_songs": total_songs,
                            "count": 0,
                        }
                    case ("UPDATE", artist_id, count):
                        p = in_progress.get(artist_id)
                        match p:
                            case None:
                                pass
                            case {
                                "task_id": task_id,
                                "total_songs": total_songs,
                                "count": current_count,
                            }:
                                progress.update(task_id, advance=count)
                                current_count += count
                                in_progress[artist_id]["count"] = current_count

                                if current_count == total_songs:
                                    # this task is complete
                                    t = in_progress.pop(artist_id)
                                    completed.append(t)

                                    # only keep 40 progress bars in our history
                                    # This is due to Rich not scrolling
                                    for i in range(
                                        40, len(in_progress) + len(completed)
                                    ):
                                        try:
                                            item = completed.pop(0)
                                            progress.update(
                                                item["task_id"], visible=False
                                            )
                                        except IndexError:
                                            pass
                            case _:
                                print("Unable to match")
                    case _:
                        print(f"ProgressWorker got unknown message {q}")
            except Empty:
                pass

            try:
                stop = stop_queue.get(timeout=0.01)
                if stop:
                    break
            except Empty:
                pass


def main():
    for i in ("NAVIDROME_URL", "NAVIDROME_USERNAME", "NAVIDROME_PASSWORD"):
        if not os.getenv(i):
            raise Exception(f"Please make sure environment variable {i} is set")

    parser = argparse.ArgumentParser(description="Subsonic Extractor")
    parser.add_argument(
        "--workers", type=int, default=8, help="Number of worker processes"
    )
    parser.add_argument(
        "--artist", type=str, action="append", help="Artist name to filter by"
    )
    args = parser.parse_args()

    song_queue = multiprocessing.Queue(maxsize=100)
    progress_queue = multiprocessing.Queue(maxsize=100)
    stop_queue = multiprocessing.Queue()

    generator_process = multiprocessing.Process(
        target=song_generator,
        args=(song_queue, progress_queue, args.workers, args.artist),
    )
    generator_process.start()

    workers = []
    for _ in range(args.workers):
        p = multiprocessing.Process(target=worker, args=(song_queue, progress_queue))
        p.start()
        workers.append(p)

    progress_bar_process = multiprocessing.Process(
        target=progress_bar_worker, args=(progress_queue, stop_queue)
    )
    progress_bar_process.start()

    for p in workers:
        p.join()

    stop_queue.put(True)

    progress_bar_process.join()
    generator_process.join()
