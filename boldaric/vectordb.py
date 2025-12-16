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
from enum import Enum

from . import feature_helper

from .models.track import Track


class TrackMetadata(BaseModel):
    subsonic_id: str
    artist: str
    album: str
    title: str


class CollectionType(Enum):
    DEFAULT = feature_helper.NormalizedFeatureHelper
    OLD = feature_helper.OldFeatureHelper
    MOOD = feature_helper.MoodFeatureHelper
    GENRE = feature_helper.GenreFeatureHelper


class VectorDB:
    def __init__(self, client: chromadb.ClientAPI):
        self.client = client
        self.collections = self._create_collections()

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

    def delete_and_recreate_collections(self):
        for c in self.collections.keys():
            self.client.delete_collection(name=c.value)

        # recreate
        self.collections = self._create_collections()

    def add_track(self, subsonic_id: str, track: Track):
        """Store a track's features"""

        # For now, use the old (default) normalization technique
        #  otherwise, some embeddings dominate.
        # A future plan, is to either:
        #  - Store un-normalized embeddings in the db, then do scaling when we query
        #  - Or, have multiple collections, each with a category of embedding (default, mood, energy, genre similarity, ...)
        for collection in CollectionType:
            embedding = collection.value.track_to_embeddings(track)

            metadata = TrackMetadata(
                subsonic_id=subsonic_id,
                artist=track.artist,
                album=track.album,
                title=track.title,
            ).model_dump()

            self.collections[collection].upsert(
                ids=subsonic_id, embeddings=[embedding], metadatas=[metadata]
            )

    def track_exists(self, collection: CollectionType, subsonic_id: str) -> bool:
        return self.get_track(sollection, subsonic_id) != None

    def get_track(self, collection: CollectionType, subsonic_id: str) -> dict | None:
        results = self.collections[collection].get(ids=[subsonic_id])
        if results and len(results["ids"]) > 0:
            return {
                "id": results["ids"][0],
                "metadata": results["metadatas"][0],
            }
        return None

    def get_all_tracks(self, collection: CollectionType) -> list[dict]:
        """Get all tracks from the database"""
        results = self.collections[collection].get(include=["embeddings", "metadatas"])

        # Process results into a list of dictionaries
        tracks = []
        for i in range(len(results["ids"])):
            tracks.append(
                {
                    "id": results["ids"][i],
                    "metadata": results["metadatas"][i],
                    "embedding": (
                        results["embeddings"][i] if "embeddings" in results else None
                    ),
                }
            )

        return tracks

    def delete_track(self, subsonic_id: str) -> None:
        """Delete a track by its subsonic_id"""
        for c in CollectionType:
            self.collections[c].delete(ids=[subsonic_id])

    def delete_tracks(self, subsonic_ids: list[str]) -> None:
        """Delete multiple tracks by their subsonic_ids"""
        if len(subsonic_ids) > 0:
            for c in CollectionType:
                self.collections[c].delete(ids=subsonic_ids)

    def delete_all_tracks(self) -> None:
        """Delete all tracks from the database"""
        for c in CollectionType:
            all_ids = self.collections[c].get(include=[])["ids"]
            if all_ids:
                self.collections[c].delete(ids=all_ids)

    def query_similar(
        self,
        collection: CollectionType,
        embedding: list[float],
        n_results: int = 5,
        ignore_songs: list[tuple[str, str]] = [],
    ) -> list[dict]:
        # query for similar items. We are going to do some filtering,
        #  so we query for 3x more results, but only return the top
        #  n_results
        results = self.collections[collection].query(
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

    ## Internal ##
    def _create_collections(self):
        for x in CollectionType:
            print(x, type(x.value))

        return dict(
            [
                (
                    x,
                    self.client.get_or_create_collection(
                        name=x.value.name(), metadata={"hnsw:space": "cosine"}
                    ),
                )
                for x in CollectionType
            ]
        )
