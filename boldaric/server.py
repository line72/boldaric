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
import random
import traceback

from pydantic import BaseModel, ValidationError, Field
from typing import Optional

from pathlib import Path
from importlib import resources

import boldaric
import boldaric.subsonic
from boldaric.records.station_options import StationOptions

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


class CreateStationParams(BaseModel):
    station_name: str = ""
    song_id: str = ""
    replay_song_cooldown: int = Field(default=50)
    replay_artist_downrank: float = Field(default=0.995)
    ignore_live: bool = Field(default=False)


class UpdateStationParams(BaseModel):
    replay_song_cooldown: int = Field(default=50)
    replay_artist_downrank: float = Field(default=0.995)
    ignore_live: bool = Field(default=False)


def get_next_songs(
    db,
    conn,
    pool,
    station_options: StationOptions,
    history: list,
    played: list[boldaric.models.track_history.TrackHistory],
    thumbs_downed: list[boldaric.models.track_history.TrackHistory],
) -> list[dict]:
    logger = logging.getLogger(__name__)
    logger.debug("get_next_song")

    # Both played and thumbs_downed are lists of TrackHistory models
    chunksize = (len(history) + pool._processes - 1) // pool._processes

    new_embeddings = boldaric.simulator.attract(pool, history, chunksize)

    # query similar
    ignore_list = []
    # ignore ALL thumbs downed
    ignore_list.extend([(x.artist, x.title) for x in thumbs_downed])
    # ignore last X played
    replay_song_cooldown = station_options.replay_song_cooldown
    ignore_list.extend([(x.artist, x.title) for x in played[-replay_song_cooldown:]])
    logger.debug(f"ignoring {ignore_list}")

    tracks = db.query_similar(new_embeddings, n_results=45, ignore_songs=ignore_list)

    # resort these, and slightly downvote recent artists
    recent_artists = [x.artist for x in played[-15:]]

    def update_similarity(t):
        replay_artist_downrank = station_options.replay_artist_downrank
        similarity = (
            replay_artist_downrank if t["metadata"]["artist"] in recent_artists else 1.0
        )
        logger.debug(
            f"similarity for {t['metadata']['artist']} {t['metadata']['title']} is {similarity}"
        )
        return {**t, "similarity": t["similarity"] * similarity}

    tracks = list(map(update_similarity, tracks))
    # Sort by similarity
    tracks.sort(key=lambda x: -x["similarity"])

    # return all tracks that have subsonic info
    tracks = list(
        filter(
            lambda t: "subsonic_id" in t["metadata"]
            and t["metadata"]["subsonic_id"] not in (None, ""),
            tracks,
        )
    )

    possible_tracks = [
        (x["metadata"]["artist"], x["metadata"]["title"], x["similarity"])
        for x in tracks
    ]
    logger.debug(f"Possible tracks {possible_tracks}")

    return tracks


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
                hashlib.sha256(salt + x.username.encode("utf-8")).hexdigest(),
                {"id": x.id, "username": x.username},
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
    try:
        data = await request.json()
        login = data["login"].strip()

        # verify
        user = request.app["station_db"].get_user(login)
        if user:
            # make a token
            salt = request.app["salt"]
            token = hashlib.sha256(salt + user.username.encode("utf-8")).hexdigest()

            return web.json_response(
                {"token": token, "id": user.id, "username": user.username}
            )
        else:
            return web.json_response({"error": "Unauthorized"}, status=401)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error in auth: {str(e)}\n{traceback.format_exc()}")
        return web.json_response({"error": "Error processing request"}, status=500)


@routes.get("/api/stations")
async def get_stations(request):
    try:
        user = request["user"]
        stations = request.app["station_db"].get_stations_for_user(user["id"])

        # Convert Station models to dictionaries for JSON serialization
        stations_dict = [
            {
                "id": station.id,
                "user_id": station.user_id,
                "name": station.name,
                "replay_song_cooldown": station.replay_song_cooldown,
                "replay_artist_downrank": station.replay_artist_downrank,
                "ignore_live": station.ignore_live,
            }
            for station in stations
        ]

        return web.json_response(stations_dict)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error in get_stations: {str(e)}\n{traceback.format_exc()}")
        return web.json_response({"error": "Error processing request"}, status=500)


@routes.post("/api/stations")
async def make_station(request):
    try:
        station_db = request.app["station_db"]
        user = request["user"]
        sub_conn = request.app["sub_conn"]

        data = await request.json()

        try:
            params = CreateStationParams(
                **{
                    k: v
                    for k, v in data.items()
                    if k in CreateStationParams.model_fields
                }
            )
        except ValidationError as e:
            return web.json_response({"error": e.errors()}, status=400)

        track = station_db.get_track_by_subsonnic_id(params.song_id)
        if not track:
            return web.json_response({"error": "Invalid `song_id`"}, status=400)

        station_id = station_db.create_station(user["id"], params.station_name)
        # set properties
        station_db.set_station_options(
            station_id,
            params.replay_song_cooldown,
            params.replay_artist_downrank,
            params.ignore_live,
        )

        station_db.add_track_to_or_update_history(station_id, track, False, SEED_RATING)

        stream_url = boldaric.subsonic.make_stream_link(sub_conn, track.subsonic_id)
        cover_url = boldaric.subsonic.make_album_art_link(sub_conn, track.subsonic_id)

        return web.json_response(
            {
                "station": {"id": station_id, "name": params.station_name},
                "track": {
                    "url": stream_url,
                    "song_id": track.subsonic_id,
                    "artist": track.artist,
                    "title": track.title,
                    "album": track.album,
                    "cover_url": cover_url,
                },
            }
        )
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error in make_station: {str(e)}\n{traceback.format_exc()}")
        return web.json_response({"error": "Error processing request"}, status=500)


@routes.get("/api/station/{station_id}")
async def get_next_song_for_station(request):
    try:
        vec_db = request.app["vec_db"]
        station_db = request.app["station_db"]
        sub_conn = request.app["sub_conn"]
        pool = request.app["pool"]
        loop = asyncio.get_running_loop()

        station_id = request.match_info["station_id"]

        # make our history...
        history = station_db.get_embedding_history(station_id)

        station_options: StationOptions = station_db.get_station_options(station_id)

        # load up the track history
        thumbs_downed = station_db.get_thumbs_downed_history(station_id)
        # get most recent 100
        played = station_db.get_track_history(
            station_id, max(100, station_options.replay_song_cooldown)
        )
        # reverse the order
        played.reverse()

        next_tracks = await loop.run_in_executor(
            None,
            lambda: get_next_songs(
                vec_db, sub_conn, pool, station_options, history, played, thumbs_downed
            ),
        )

        # grab 3 choices based upon similarity
        def get_random(tracks):
            if len(tracks) == 0:
                return None

            choice = random.choices(
                tracks, weights=[item["similarity"] for item in tracks], k=1
            )[0]
            # modify the original list here
            tracks.remove(choice)
            return choice

        top_tracks = [
            get_random(next_tracks),
            get_random(next_tracks),
            get_random(next_tracks),
        ]
        top_tracks = [x for x in top_tracks if x is not None]

        if len(top_tracks) > 0:

            def make_response(t):
                track = station_db.get_track_by_subsonnic_id(
                    t["metadata"]["subsonic_id"]
                )
                stream_url = boldaric.subsonic.make_stream_link(
                    sub_conn, track.subsonic_id
                )
                cover_url = boldaric.subsonic.make_album_art_link(
                    sub_conn, track.subsonic_id
                )

                return {
                    "url": stream_url,
                    "song_id": track.subsonic_id,
                    "artist": track.artist,
                    "title": track.title,
                    "album": track.album,
                    "cover_url": cover_url,
                }

            return web.json_response(
                {"tracks": list(map(lambda t: make_response(t), top_tracks))}
            )
        else:
            return web.json_response({"error": "Unable to find next song"}, status=400)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(
            f"Error in get_next_song_for_station: {str(e)}\n{traceback.format_exc()}"
        )
        return web.json_response({"error": "Error processing request"}, status=500)


@routes.get("/api/station/{station_id}/info")
async def get_station_info(request):
    try:
        user = request["user"]
        station_id = request.match_info["station_id"]

        station = request.app["station_db"].get_station(user["id"], station_id)

        if station:
            station_dict = {
                "id": station.id,
                "user_id": station.user_id,
                "name": station.name,
                "replay_song_cooldown": station.replay_song_cooldown,
                "replay_artist_downrank": station.replay_artist_downrank,
                "ignore_live": station.ignore_live,
            }
            return web.json_response(station_dict)
        else:
            return web.json_response({"error": "Station not found"}, status=404)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error in get_station_info: {str(e)}\n{traceback.format_exc()}")
        return web.json_response({"error": "Error processing request"}, status=500)


@routes.put("/api/station/{station_id}/info")
async def update_station_info(request):
    try:
        user = request["user"]
        station_db = request.app["station_db"]
        station_id = request.match_info["station_id"]

        data = await request.json()

        try:
            params = UpdateStationParams(
                **{
                    k: v
                    for k, v in data.items()
                    if k in UpdateStationParams.model_fields
                }
            )
        except ValidationError as e:
            return web.json_response({"error": e.errors()}, status=400)

        # Update station options
        station_db.set_station_options(
            station_id,
            params.replay_song_cooldown,
            params.replay_artist_downrank,
            params.ignore_live,
        )

        # Get updated station to return current values
        station = station_db.get_station(user["id"], station_id)
        if station:
            station_dict = {
                "id": station.id,
                "user_id": station.user_id,
                "name": station.name,
                "replay_song_cooldown": station.replay_song_cooldown,
                "replay_artist_downrank": station.replay_artist_downrank,
                "ignore_live": station.ignore_live,
            }
            return web.json_response(station_dict)
        else:
            return web.json_response({"error": "Station not found"}, status=404)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(
            f"Error in update_station_info: {str(e)}\n{traceback.format_exc()}"
        )
        return web.json_response({"error": "Error processing request"}, status=500)


@routes.post("/api/station/{station_id}/seed")
async def add_seed(request):
    try:
        data = await request.json()

        station_db = request.app["station_db"]

        station_id = request.match_info["station_id"]
        song_id = data["song_id"].strip()

        track = station_db.get_track_by_subsonic_id(song_id)

        track_history_id = station_db.add_track_to_or_update_history(
            station_id, track, False, SEED_RATING
        )

        return web.json_response({"success": True})
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error in add_seed: {str(e)}\n{traceback.format_exc()}")
        return web.json_response({"error": "Error processing request"}, status=500)


@routes.put("/api/station/{station_id}/{song_id}")
async def add_song_to_history(request):
    try:
        station_db = request.app["station_db"]

        station_id = request.match_info["station_id"]
        song_id = request.match_info["song_id"]

        track = station_db.get_track_by_subsonic_id(song_id)
        track_history_id = station_db.add_track_to_or_update_history(
            station_id, track, False, DEFAULT_RATING
        )

        return web.json_response({"success": True})
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(
            f"Error in add_song_to_history: {str(e)}\n{traceback.format_exc()}"
        )
        return web.json_response({"error": "Error processing request"}, status=500)


@routes.post("/api/station/{station_id}/{song_id}/thumbs_up")
async def thumbs_up(request):
    try:
        station_db = request.app["station_db"]

        station_id = request.match_info["station_id"]
        song_id = request.match_info["song_id"]

        track = station_db.get_track_by_subsonic_id(song_id)
        track_history_id = station_db.add_track_to_or_update_history(
            station_id, track, False, THUMBS_UP_RATING
        )

        return web.json_response({"success": True})
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error in thumbs_up: {str(e)}\n{traceback.format_exc()}")
        return web.json_response({"error": "Error processing request"}, status=500)


@routes.post("/api/station/{station_id}/{song_id}/thumbs_down")
async def thumbs_down(request):
    try:
        station_db = request.app["station_db"]

        station_id = request.match_info["station_id"]
        song_id = request.match_info["song_id"]

        track = station_db.get_track_by_subsonic_id(song_id)
        track_history_id = station_db.add_track_to_or_update_history(
            station_id, track, True, THUMBS_DOWN_RATING
        )

        return web.json_response({"success": True})
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error in thumbs_down: {str(e)}\n{traceback.format_exc()}")
        return web.json_response({"error": "Error processing request"}, status=500)


@routes.get("/api/search")
async def search(request):
    try:
        sub_conn = request.app["sub_conn"]
        artist = request.query["artist"]
        title = request.query["title"]

        results = boldaric.subsonic.search_songs(sub_conn, f"{artist} {title}")

        return web.json_response(results)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error in search: {str(e)}\n{traceback.format_exc()}")
        return web.json_response({"error": "Error processing request"}, status=500)


def initialize_database(db_path):
    """Initialize database for Alembic migrations."""
    from alembic import command
    from alembic.config import Config

    # Check if database exists
    db_exists = os.path.exists(db_path)

    if db_exists:
        # Database exists, stamp it
        alembic_ini_path = resources.files("boldaric").joinpath("alembic.ini")
        alembic_cfg = Config(str(alembic_ini_path))

        # Override script_location to be absolute
        alembic_dir = os.path.join(os.path.dirname(alembic_ini_path), "alembic")
        alembic_cfg.set_main_option("script_location", alembic_dir)
        alembic_cfg.set_main_option(
            "path_separator", os.pathsep
        )  # Fix for Alembic warning
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
        command.stamp(alembic_cfg, "initial")
        print(f"Existing database at {db_path} stamped for migrations")
    else:
        # Database doesn't exist, create it and run migrations
        # Create database file
        with open(db_path, "w") as f:
            pass

        # Run migrations
        alembic_ini_path = resources.files("boldaric").joinpath("alembic.ini")
        alembic_cfg = Config(str(alembic_ini_path))
        alembic_cfg.set_main_option(
            "path_separator", os.pathsep
        )  # Fix for Alembic warning
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
        command.upgrade(alembic_cfg, "head")
        print(f"New database created at {db_path} with migrations applied")


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
    parser.add_argument(
        "--initialize-db",
        action="store_true",
        help="Initialize database for migrations and exit",
    )

    args = parser.parse_args()

    # set up the logger
    log_level = logging.DEBUG if args.verbose else logging.INFO

    logging.basicConfig(
        level=log_level,  # Set minimum level to show
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler()],  # Console output
    )

    # Handle database initialization
    if args.initialize_db:
        db_file = os.path.join(args.db_path, "stations.db")
        initialize_database(db_file)
        return

    asyncio.run(go(args.db_path, args.port))


if __name__ == "__main__":
    main()
