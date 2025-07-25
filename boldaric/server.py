# Copyright (c) 2025 Marcus Dillavou <line72@line72.net>
# Part of the Boldaric Project:
#  https://github.com/line72/boldaric
# Released under the AGPLv3 or later

# Web Server for the boldaric project
#
# This provides a RESTful API for creating stations, getting next
# tracks for a stations, rating songs, seeding songs, and so on.

from aiohttp import web
import asyncio
import multiprocessing

import argparse
import os
import hashlib
import logging

from pathlib import Path

import boldaric
import boldaric.subsonic

# Development mode path
DEV_RESOURCES = Path(__file__).parent.parent / "resources"

# Installed mode path (system-wide: /usr/share/my_project/resources)
INSTALLED_RESOURCES = Path("/usr/share") / "my_project" / "resources"

# Choose appropriate path based on environment
resources_path = DEV_RESOURCES if os.path.exists(DEV_RESOURCES) else INSTALLED_RESOURCES

DEFAULT_RATING = 3
SEED_RATING = 8
THUMBS_UP_RATING = 5
THUMBS_DOWN_RATING = -3


routes = web.RouteTableDef()


def get_next_song(db, conn, pool, history, played, thumbs_downed):
    logger = logging.getLogger(__name__)
    logger.debug("get_next_song")

    # Both played and thumbs_downed are a list of 3-item tuples, where
    # each tuple is: (artist, title, album)
    chunksize = (len(history) + pool._processes - 1) // pool._processes

    averages = boldaric.simulator.attract(pool, history, chunksize)
    new_features = boldaric.feature_helper.list_to_features(averages)

    # query similar
    ignore_list = []
    # ignore ALL thumbs downed
    ignore_list.extend([(x[0], x[1]) for x in thumbs_downed])
    # ignore last 80 played
    ignore_list.extend([(x[0], x[1]) for x in played[-80:]])
    logger.debug(f"ignoring {ignore_list}")

    tracks = db.query_similar(new_features, n_results=45, ignore_songs=ignore_list)

    # resort these, and slightly downvote recent artists
    recent_artists = [x[0] for x in played[-15:]]

    def update_similarity(t):
        similarity = 0.995 if t["metadata"]["artist"] in recent_artists else 1.0
        logger.debug(
            f"similarity for {t['metadata']['artist']} {t['metadata']['title']} is {similarity}"
        )
        return {**t, "similarity": t["similarity"] * similarity}

    tracks = list(map(update_similarity, tracks))
    # Sort by similarity
    tracks.sort(key=lambda x: -x["similarity"])

    possible_tracks = [
        (x["metadata"]["artist"], x["metadata"]["title"], x["similarity"])
        for x in tracks
    ]
    logger.debug(f"Possible tracks {possible_tracks}")

    for track in tracks:
        if "subsonic_id" in track["metadata"] and track["metadata"][
            "subsonic_id"
        ] not in (None, ""):
            logger.info(
                f"next song is {track['metadata']['artist']} - {track['metadata']['album']} - {track['metadata']['title']}"
            )
            return track

    return None


@web.middleware
async def auth_middleware(request, handler):
    # Skip auth for non-api routes and the auth endpoint
    if not request.path.startswith("/api") or request.path == "/api/auth":
        return await handler(request)

    # salt
    salt = request.app["salt"]
    user_salts = dict(
        [
            (
                hashlib.sha256(salt + x[1].encode("utf-8")).hexdigest(),
                {"id": x[0], "username": x[1]},
            )
            for x in request.app["station_db"].get_all_users()
        ]
    )

    # For all other routes, require Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return web.json_response({"error": "Unauthorized"}, status=401)

    auth_token = auth_header[7:]

    user = user_salts.get(auth_token)
    if not user:
        return web.json_response({"error": "Unauthorized"}, status=401)

    # Store this user in the request
    request["user"] = user

    return await handler(request)


@routes.post("/api/auth")
async def auth(request):
    data = await request.json()
    login = data["login"].strip()

    # verify
    user = request.app["station_db"].get_user(login)
    if user:
        # make a token
        salt = request.app["salt"]
        token = hashlib.sha256(salt + user["username"].encode("utf-8")).hexdigest()

        return web.json_response(
            {"token": token, "id": user["id"], "username": user["username"]}
        )
    else:
        return web.json_response({"error": "Unauthorized"}, status=401)


@routes.get("/api/stations")
async def get_stations(request):
    user = request["user"]
    stations = request.app["station_db"].get_stations_for_user(user["id"])

    return web.json_response(stations)


@routes.post("/api/stations")
async def make_station(request):
    vec_db = request.app["vec_db"]
    station_db = request.app["station_db"]
    user = request["user"]
    sub_conn = request.app["sub_conn"]

    data = await request.json()
    station_name = data.get("station_name")
    song_id = data.get("song_id")

    if not station_name:
        return web.json_response(
            {"error": "Missing parameters `station_name`"}, status=400
        )
    if not song_id:
        return web.json_response({"error": "Missing parameters `song_id`"}, status=400)

    track = vec_db.get_track(song_id)
    if not track:
        return web.json_response({"error": "Invalid `song_id`"}, status=400)

    station_id = station_db.create_station(user["id"], station_name)

    track_features = boldaric.feature_helper.features_to_list(track["features"])

    # Add this as seed data with a thumbs up rating
    track_history_id = station_db.add_track_to_or_update_history(
        station_id,
        track["metadata"]["subsonic_id"],
        track["metadata"]["artist"],
        track["metadata"]["title"],
        track["metadata"]["album"],
        False,
    )

    station_db.add_embedding_history(
        station_id, track_history_id, track_features, SEED_RATING
    )

    stream_url = boldaric.subsonic.make_stream_link(sub_conn, track)
    cover_url = boldaric.subsonic.make_album_art_link(sub_conn, track)

    return web.json_response(
        {
            "station": {"id": station_id, "name": station_name},
            "track": {
                "url": stream_url,
                "song_id": track["metadata"]["subsonic_id"],
                "artist": track["metadata"]["artist"],
                "title": track["metadata"]["title"],
                "album": track["metadata"]["album"],
                "cover_url": cover_url,
            },
        }
    )


@routes.get("/api/station/{station_id}")
async def get_next_song_for_station(request):
    vec_db = request.app["vec_db"]
    station_db = request.app["station_db"]
    sub_conn = request.app["sub_conn"]
    pool = request.app["pool"]
    loop = asyncio.get_running_loop()

    station_id = request.match_info["station_id"]

    # make our history...
    history = boldaric.simulator.make_history()
    embeddings = station_db.get_embedding_history(station_id)

    for embedding, rating in embeddings:
        history = boldaric.simulator.add_history(history, embedding, rating)

    # load up the track history
    thumbs_downed = station_db.get_thumbs_downed_history(station_id)
    # get most recent 100
    played = station_db.get_track_history(station_id, 100)
    # reverse the order
    played.reverse()

    next_track = await loop.run_in_executor(
        None,
        lambda: get_next_song(vec_db, sub_conn, pool, history, played, thumbs_downed),
    )

    if next_track:
        stream_url = boldaric.subsonic.make_stream_link(sub_conn, next_track)
        cover_url = boldaric.subsonic.make_album_art_link(sub_conn, next_track)

        # go head an add this. The user might thumbs up/down this
        #  track, and we'll just modify if that's the case
        track_history_id = station_db.add_track_to_or_update_history(
            station_id,
            next_track["metadata"]["subsonic_id"],
            next_track["metadata"]["artist"],
            next_track["metadata"]["title"],
            next_track["metadata"]["album"],
            False,
        )
        feature_list = boldaric.feature_helper.features_to_list(next_track["features"])
        station_db.add_embedding_history(
            station_id, track_history_id, feature_list, DEFAULT_RATING
        )

        return web.json_response(
            {
                "url": stream_url,
                "song_id": next_track["metadata"]["subsonic_id"],
                "artist": next_track["metadata"]["artist"],
                "title": next_track["metadata"]["title"],
                "album": next_track["metadata"]["album"],
                "cover_url": cover_url,
            }
        )
    else:
        return web.json_response({"error": "Unable to find next song"}, status=400)


@routes.post("/api/station/{station_id}/seed")
async def add_seed(request):
    data = await request.json()

    vec_db = request.app["vec_db"]
    station_db = request.app["station_db"]

    station_id = request.match_info["station_id"]
    song_id = data["song_id"].strip()

    track = vec_db.get_track(song_id)
    feature_list = boldaric.feature_helper.features_to_list(track["features"])

    track_history_id = station_db.add_track_to_or_update_history(
        station_id,
        track["metadata"]["subsonic_id"],
        track["metadata"]["artist"],
        track["metadata"]["title"],
        track["metadata"]["album"],
        False,
    )
    station_db.add_embedding_history(
        station_id, track_history_id, feature_list, SEED_RATING
    )

    return web.json_response({"success": True})


@routes.post("/api/station/{station_id}/{song_id}/thumbs_up")
async def thumbs_up(request):
    vec_db = request.app["vec_db"]
    station_db = request.app["station_db"]

    station_id = request.match_info["station_id"]
    song_id = request.match_info["song_id"]

    track = vec_db.get_track(song_id)
    feature_list = boldaric.feature_helper.features_to_list(track["features"])

    track_history_id = station_db.add_track_to_or_update_history(
        station_id,
        track["metadata"]["subsonic_id"],
        track["metadata"]["artist"],
        track["metadata"]["title"],
        track["metadata"]["album"],
        False,
    )
    station_db.add_embedding_history(
        station_id, track_history_id, feature_list, THUMBS_UP_RATING
    )

    return web.json_response({"success": True})


@routes.post("/api/station/{station_id}/{song_id}/thumbs_down")
async def thumbs_down(request):
    vec_db = request.app["vec_db"]
    station_db = request.app["station_db"]

    station_id = request.match_info["station_id"]
    song_id = request.match_info["song_id"]

    track = vec_db.get_track(song_id)
    feature_list = boldaric.feature_helper.features_to_list(track["features"])

    track_history_id = station_db.add_track_to_or_update_history(
        station_id,
        track["metadata"]["subsonic_id"],
        track["metadata"]["artist"],
        track["metadata"]["title"],
        track["metadata"]["album"],
        True,
    )
    station_db.add_embedding_history(
        station_id, track_history_id, feature_list, THUMBS_DOWN_RATING
    )

    return web.json_response({"success": True})


@routes.get("/api/search")
async def search(request):
    sub_conn = request.app["sub_conn"]
    artist = request.query["artist"]
    title = request.query["title"]

    results = boldaric.subsonic.search_songs(sub_conn, f"{artist} {title}")

    return web.json_response(results)


async def go(db_path, port):
    for i in ("NAVIDROME_URL", "NAVIDROME_USERNAME", "NAVIDROME_PASSWORD"):
        if not os.getenv(i):
            raise Exception(f"Please make sure environment variable {i} is set")

    # create some things to store in our app state
    vec_db = boldaric.VectorDB.build_from_http()
    station_db = boldaric.StationDB(os.path.join(db_path, "stations.db"))
    sub_conn = boldaric.subsonic.make_from_parameters(
        os.getenv("NAVIDROME_URL"),
        os.getenv("NAVIDROME_USERNAME"),
        os.getenv("NAVIDROME_PASSWORD"),
    )

    # generate a common pool we'll use for multiprocessing
    # Not creating/throwing this away speed things up
    pool = multiprocessing.Pool()

    # Generate a salt that we'll use for auth
    salt = os.urandom(16)

    app = web.Application(middlewares=[auth_middleware])
    app.add_routes(routes)

    app["vec_db"] = vec_db
    app["station_db"] = station_db
    app["sub_conn"] = sub_conn
    app["pool"] = pool
    app["salt"] = salt

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    await asyncio.Future()


def main():
    parser = argparse.ArgumentParser(description="Boldaric Web Server")
    parser.add_argument(
        "-d",
        "--db-path",
        default="./db",
        dest="db_path",
        help="Path to the station database",
    )
    parser.add_argument(
        "-p", "--port", type=int, default=8765, help="Port to run the web server on"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # set up the logger
    log_level = logging.DEBUG if args.verbose else logging.INFO

    logging.basicConfig(
        level=log_level,  # Set minimum level to show
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler()],  # Console output
    )

    asyncio.run(go(args.db_path, args.port))


if __name__ == "__main__":
    main()
