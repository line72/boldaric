# Copyright (c) 2025 Marcus Dillavou <line72@line72.net>
# Part of the Boldaric Project:
#  https://github.com/line72/boldaric
# Released under the AGPLv3 or later

# VectorDB is a wrapper around chroma.
#
# Everything is stored in a collection called
#  `audio_features`. Documents are stored using the subonic_id as the
#  primary key. This class allows inserting and updating track
#  embeddings, along with lookup, and similarity searches.

import json

import chromadb

import numpy as np

from pydantic import BaseModel

from . import feature_helper

from .models.track import Track

# Hard-coded to the number of dimension we extract
DIMENSIONS = 148


class TrackMetadata(BaseModel):
    subsonic_id: str
    artist: str
    album: str
    title: str


class VectorDB:
    def __init__(self, client: chromadb.ClientAPI):
        collection_name = "audio_features"

        self.client = client
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "dimension": DIMENSIONS},
        )

    @staticmethod
    def build_from_path(path: str) -> "VectorDB":
        client = chromadb.PersistentClient(path=path)
        return VectorDB(client)

    @staticmethod
    def build_from_http(host: str = "localhost", port: int = 8000) -> "VectorDB":
        # https://docs.trychroma.com/docs/run-chroma/client-server
        #
        # Make sure the server is running by first doing:
        #  `chroma run --path /db_path`
        #
        client = chromadb.HttpClient(
            host=host,
            port=port,
            settings=chromadb.Settings(anonymized_telemetry=False),
        )
        return VectorDB(client)

    def add_track(self, subsonic_id: str, track: Track):
        """Store a track's features"""
        embedding = feature_helper.track_to_embeddings(track)

        metadata = TrackMetadata(
            subsonic_id=subsonic_id,
            artist=track.artist,
            album=track.album,
            title=track.track,
        ).model_dump()

        self.collection.upsert(
            ids=subsonic_id, embeddings=[embedding], metadatas=[metadata]
        )

    def track_exists(self, subsonic_id: str) -> bool:
        return self.get_track(subsonic_id) != None

    def get_track(self, subsonic_id: str) -> dict | None:
        results = self.collection.get(ids=[subsonic_id])
        if results and len(results["ids"]) > 0:
            return {
                "id": results["ids"][0],
                "metadata": results["metadatas"][0],
            }
        return None

    def get_all_tracks(self) -> list[dict]:
        """Get all tracks from the database"""
        results = self.collection.get(
            include=["embeddings", "metadatas"]
        )
        
        # Process results into a list of dictionaries
        tracks = []
        for i in range(len(results["ids"])):
            tracks.append({
                "id": results["ids"][i],
                "metadata": results["metadatas"][i],
                "embedding": results["embeddings"][i] if "embeddings" in results else None
            })
        
        return tracks

    def delete_track(self, subsonic_id: str) -> None:
        """Delete a track by its subsonic_id"""
        self.collection.delete(ids=[subsonic_id])

    def delete_tracks(self, subsonic_ids: list[str]) -> None:
        """Delete multiple tracks by their subsonic_ids"""
        self.collection.delete(ids=subsonic_ids)

    def delete_all_tracks(self) -> None:
        """Delete all tracks from the database"""
        all_ids = self.collection.get(include=[])["ids"]
        if all_ids:
            self.collection.delete(ids=all_ids)

    def query_similar(
        self,
        embedding: list[float],
        n_results: int = 5,
        ignore_songs: list[tuple[str, str]] = [],
    ) -> list[dict]:
        # query for similar items. We are going to do some filtering,
        #  so we query for 3x more results, but only return the top
        #  n_results
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results * 3,
            include=["embeddings", "metadatas", "distances"],
        )

        # Process the results
        final_results = []

        # Iterate through our results and attach some metadata, filter
        # out ignored items, and resort
        for result_meta, distance, result_embedding, result_id in zip(
            results["metadatas"][0],
            results["distances"][0],
            results["embeddings"][0],
            results["ids"][0],
        ):
            # Ignore anything in the ignore list
            result_tuple = (result_meta.get("artist", ""), result_meta.get("title", ""))
            if result_tuple in ignore_songs:
                continue

            final_results.append(
                {"id": result_id, "metadata": result_meta, "similarity": 1 - distance}
            )

        # resort
        final_results.sort(key=lambda x: -x["similarity"])

        return final_results[:n_results]
