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

# Hard-coded to the number of dimension we extract
DIMENSIONS = 148


class TrackMetadata(BaseModel):
    path: str
    artist: str
    album: str
    title: str
    year: str
    rating: float = 0.0
    tagged_genres: list[str]
    predicted_genres: list[dict]
    mood: dict
    technical: dict
    features: dict
    musicbrainz_ids: dict
    subsonic_id: str


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

    def add_track(self, subsonic_id: str, features: dict):
        """Store a track's features"""
        meta = features.get("metadata", {})

        embedding = feature_helper.features_to_embeddings(features)

        metadata = TrackMetadata(
            path=meta.get("path", ""),
            artist=meta.get("artist", "Unknown Artist"),
            album=meta.get("album", "Unknown Album"),
            title=meta.get("title", "Unknown Track"),
            year=meta.get("date", "")[:4],
            tagged_genres=meta.get("genre", []),
            predicted_genres=features.get("genre", []),
            mood=features.get("mood", {}).get("probabilities", {}),
            technical={
                "duration": meta.get("duration", 0),
                "sample_rate": meta.get("sample_rate", 44100),
                "bit_depth": meta.get("bit_depth", 16),
                "channels": meta.get("channels", 2),
                "loudness": features.get("loudness"),
                "dynamic_complexity": features.get("dynamic_complexity"),
            },
            features={
                "rhythm": features.get("groove", {}),
                "harmony": features.get("key", {}),
                "timbral": features.get("spectral_character", {}),
                "mfcc": features.get("mfcc", {}),
                "vocal": features.get("vocal", {}),
            },
            musicbrainz_ids={
                k: v for k, v in meta.items() if k.startswith("musicbrainz")
            },
            subsonic_id=subsonic_id,
        ).model_dump()

        # Stringify list-based fields
        metadata["tagged_genres"] = "; ".join(metadata["tagged_genres"])
        metadata["predicted_genres"] = json.dumps(metadata["predicted_genres"])

        # Store musicbrainz IDs
        musicbrainz_trackid = metadata["musicbrainz_ids"].get(
            "musicbrainz_releasetrackid", ""
        )
        if isinstance(musicbrainz_trackid, str):
            musicbrainz_trackid = (
                musicbrainz_trackid.split("'")[-1].split('"')[-1].strip()
            )
        metadata["musicbrainz_trackid"] = musicbrainz_trackid

        # Remove complex structures
        metadata.pop("features", None)
        metadata.pop("musicbrainz_ids", None)

        # Flatten metadata
        mood_data = metadata.pop("mood", {})
        for key, value in mood_data.items():
            metadata[f"mood_{key}"] = float(value)

        tech_data = metadata.pop("technical", {})
        for key, value in tech_data.items():
            metadata[f"tech_{key}"] = str(value)  # Always store as string

        # Use the subsonic id as the doc id
        doc_id = subsonic_id
        self.collection.upsert(
            ids=doc_id,
            embeddings=[embedding],
            metadatas=[metadata],
            documents=json.dumps(features),
        )

    def track_exists(self, subsonic_id: str) -> bool:
        return self.get_track(subsonic_id) != None

    def get_track(self, subsonic_id: str) -> dict | None:
        results = self.collection.get(ids=[subsonic_id])
        if results and len(results["ids"]) > 0:
            return {
                "id": results["ids"][0],
                "metadata": results["metadatas"][0],
                "features": json.loads(results["documents"][0]),
            }
        return None

    def query_similar(
        self,
        features: dict,
        n_results: int = 5,
        ignore_songs: list[tuple[str, str]] = [],
        debug: bool = False,
    ) -> list[dict]:
        embedding = feature_helper.features_to_embeddings(features)

        # query for similar items. We are going to do some filtering,
        #  so we query for 3x more results, but only return the top
        #  n_results
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results * 3,
            include=["embeddings", "metadatas", "distances", "documents"],
        )

        # Process the results
        final_results = []

        # Iterate through our results and attach some metadata, filter
        # out ignored items, and resort
        for result_meta, distance, result_embedding, result_id, doc in zip(
            results["metadatas"][0],
            results["distances"][0],
            results["embeddings"][0],
            results["ids"][0],
            results["documents"][0],
        ):
            # Ignore anything in the ignore list
            result_tuple = (result_meta.get("artist", ""), result_meta.get("title", ""))
            if result_tuple in ignore_songs:
                continue

            query_embedding = np.array(embedding)
            result_features = json.loads(doc)
            result_artist = result_meta.get("artist", "Unknown")

            similarities_and_contributions = feature_helper.calculate_similarities(
                query_embedding, result_embedding, distance
            )

            final_results.append(
                {
                    "id": result_id,
                    "metadata": result_meta,
                    "similarity": 1 - distance,
                    "features": result_features,
                    "artist": result_artist,
                    **similarities_and_contributions,
                }
            )

        # resort
        final_results.sort(key=lambda x: -x["similarity"])

        if debug:
            feature_helper.print_similarities(final_results, n_results)

        return final_results[:n_results]
