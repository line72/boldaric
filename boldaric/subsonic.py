# Copyright (c) 2025 Marcus Dillavou <line72@line72.net>
# Part of the Boldaric Project:
#  https://github.com/line72/boldaric
# Released under the AGPLv3 or later

# Web Server for the boldaric project
#
# This provides a RESTful API for creating stations, getting next
# tracks for a stations, rating songs, seeding songs, and so on.

import libsonic


def make_from_parameters(url: str, username: str, password: str, port: int = 443):
    c = libsonic.Connection(url, username, password, port=port)
    c.ping()

    return c


def make_stream_link(conn, track):
    # !mwd - this is a bit hacky, but we can use some internals
    #  to generate a pre-authed URL to directly stream
    q = conn._getQueryDict({"id": track["metadata"]["subsonic_id"]})
    req = conn._getRequest("stream.view", q)

    full_url = f"{req.full_url}?{req.data.decode('utf-8')}"
    return full_url


def make_album_art_link(conn, track):
    # !mwd - this is a bit hacky, but we can use some internals
    #  to generate a pre-authed URL to directly stream
    q = conn._getQueryDict({"id": track["metadata"]["subsonic_id"]})
    req = conn._getRequest("getCoverArt.view", q)

    full_url = f"{req.full_url}?{req.data.decode('utf-8')}"
    return full_url


def search_songs(conn, query):
    search = conn.search3(query=query, artistCount=0, albumCount=0)

    results = []
    if "searchResult3" in search and "song" in search["searchResult3"]:
        for s in search["searchResult3"]["song"]:
            results.append(
                {
                    "id": s["id"],
                    "artist": s["artist"],
                    "album": s["album"],
                    "title": s["title"],
                }
            )

    return results
