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
from sklearn.metrics.pairwise import cosine_similarity

from pydantic import BaseModel

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

        embedding = self.features_to_embeddings(features)

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
        embedding = self.features_to_embeddings(features)

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
            
            similarities_and_contributions = self.calculate_similarities(
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
            self.print_similarities(final_results, n_results)

        return final_results[:n_results]

    def features_to_embeddings(self, features: dict) -> list[float]:
        # Create a combined embedding
        embedding = []

        # 1. Genre Embeddings (128D)
        genre_embeds = np.array(
            features.get("genre_embeddings", np.zeros(128))
        ).flatten()
        # This shouldn't happen, but make sure we are at 128
        genre_embeds = (
            genre_embeds[:128]
            if len(genre_embeds) >= 128
            else np.pad(genre_embeds, (0, 128 - len(genre_embeds)))
        )
        # Do some normalization, otherwise this
        #  may dominate other features in lookups
        genre_norm = np.linalg.norm(genre_embeds)
        if genre_norm > 1e-9:
            genre_embeds = genre_embeds / genre_norm
        embedding.extend(genre_embeds.tolist())

        # 2. MFCC features (13D)
        mfcc_stats = features.get("mfcc", {})
        mfcc_means = np.array(mfcc_stats.get("mean", np.zeros(13)))[:13]
        
        # Normalize the entire MFCC vector rather than per-feature
        norm = np.linalg.norm(mfcc_means)
        if norm > 1e-9:
            mfcc_means = mfcc_means / norm
            
        embedding.extend(mfcc_means.tolist())

        # 3. Groove features (2D)
        groove = features.get("groove", {})
        danceability = max(0, min(1, groove.get("danceability", 0.5)))
        tempo_stability = max(0, min(1, groove.get("tempo_stability", 0.5)))
        embedding.extend([danceability, tempo_stability])

        # 4. Mood features (5D)
        mood_probs = features.get("mood", {}).get("probabilities", {})
        mood_features = [
            mood_probs.get("aggressive", 0.5),
            mood_probs.get("happy", 0.5),
            mood_probs.get("party", 0.5),
            mood_probs.get("relaxed", 0.5),
            mood_probs.get("sad", 0.5),
        ]
        # Apply sigmoid activation
        mood_features = 1 / (1 + np.exp(-np.array(mood_features)))
        embedding.extend(mood_features.tolist())

        # !mwd - My AI Agent suggest that I should have been
        #  normalizing the full embedding in additional to normalizing
        #  each feature. In earlier versions, I was not doing this. If
        #  you have an old database, you'll need to run the
        #  `scripts/fix-embedding-normalization.py` to migrate the
        #  embeddings.
        #
        # Normalize the full embedding vector
        embedding = np.array(embedding)
        embedding /= np.linalg.norm(embedding)

        return embedding.tolist()

    def calculate_similarities(self, query_embedding, result_embedding, distance):
        "Try to quantify similarities in different dimensions, since we know what our embeddings mean"
        # Calculate feature contributions
        query_genre = query_embedding[:128]
        query_mfcc = query_embedding[128:141]
        query_groove = query_embedding[141:143]
        query_mood = query_embedding[143:]

        result_genre = result_embedding[:128]
        result_mfcc = result_embedding[128:141]
        result_groove = result_embedding[141:143]
        result_mood = result_embedding[143:]

        genre_similarity = cosine_similarity([query_genre], [result_genre])[0][0]
        mfcc_similarity = cosine_similarity([query_mfcc], [result_mfcc])[0][0]
        groove_similarity = cosine_similarity([query_groove], [result_groove])[0][0]
        mood_similarity = cosine_similarity([query_mood], [result_mood])[0][0]

        total_similarity = 1 - distance
        genre_contribution = (
            (genre_similarity * 128 / 148) / total_similarity * 100
            if total_similarity > 0
            else 0
        )
        mfcc_contribution = (
            (mfcc_similarity * 13 / 148) / total_similarity * 100
            if total_similarity > 0
            else 0
        )
        groove_contribution = (
            (groove_similarity * 2 / 148) / total_similarity * 100
            if total_similarity > 0
            else 0
        )
        mood_contribution = (
            (mood_similarity * 5 / 148) / total_similarity * 100
            if total_similarity > 0
            else 0
        )

        return {
            "feature_contributions": {
                "genre": genre_contribution,
                "mfcc": mfcc_contribution,
                "groove": groove_contribution,
                "mood": mood_contribution,
            },
            "component_similarities": {
                "genre": genre_similarity,
                "mfcc": mfcc_similarity,
                "groove": groove_similarity,
                "mood": mood_similarity,
            },
        }

    def print_similarities(self, final_results, n_results):
        for result in final_results[:n_results]:
            print(f"ID: {result['id']}")
            print(f"Similarity: {result['similarity']:.4f}")
            print("Feature Contributions:")
            for feature, contribution in result["feature_contributions"].items():
                print(f"  {feature.capitalize()}: {contribution:.1f}%")
            print("Component Similarities:")
            for component, similarity in result["component_similarities"].items():
                print(f"  {component.capitalize()}: {similarity:.4f}")
            print()
