#!/usr/bin/env python3
#
# In the original prototype, our VectorDB, in the
# `features_to_embeddings` funtion, we were not normalizing the final
# embedding which could cause individual embeddings to dominate
# similarity look-ups.
#
# This script takes an old database with un-normalized embeddings and
# normalizes them.


import os
import shutil
import numpy as np
import chromadb
from chromadb.api.types import Embedding, Document, ID, OneOrMany, Include, Metadata
import json

from boldaric.vectordb import features_to_embeddings
from sklearn.metrics.pairwise import cosine_similarity


def migrate_database(src_path: str, dst_path: str) -> None:
    """
    Migrate a ChromaDB database from src_path to dst_path,
    normalizing all embeddings in the process.
    
    Args:
        src_path: Path to the source database
        dst_path: Path where the normalized database will be created
    """
    if os.path.exists(dst_path):
        raise ValueError(f"Destination path '{dst_path}' already exists")
    
    # Create new database
    shutil.copytree(src_path, dst_path)
    
    # Open both databases
    src_client = chromadb.PersistentClient(path=src_path)
    dst_client = chromadb.PersistentClient(path=dst_path)
    
    # Get all collections (we expect just "audio_features")
    collections = src_client.list_collections()
    
    for collection in collections:
        src_collection = src_client.get_collection(name=collection.name)
        dst_collection = dst_client.get_collection(name=collection.name)
        
        print(f"Processing collection: {collection.name}")
        
        # Get all data from source collection
        results = src_collection.get(include=["embeddings", "metadatas", "documents", "uris", "data"])
        
        ids = results["ids"]
        embeddings = results["embeddings"]
        metadatas = results["metadatas"]
        documents = results["documents"]
        uris = results["uris"]
        data = results["data"]
        
        # Recompute embeddings from original features
        normalized_embeddings = []
        for idx, doc in enumerate(results["documents"]):
            features = json.loads(doc)
            new_embedding = features_to_embeddings(features)
            normalized_embeddings.append(new_embedding)
            
            if idx % 100 == 0 and idx > 0:
                print(f"Recomputed {idx}/{len(embeddings)} embeddings...")
        
        print(f"Finished normalizing {len(normalized_embeddings)} embeddings")
        
        # Delete all existing data in destination collection
        dst_collection.delete(ids=ids)
        
        # Insert normalized data
        print("Inserting normalized embeddings into destination database...")
        dst_collection.add(
            ids=ids,
            embeddings=normalized_embeddings,
            metadatas=metadatas,
            documents=documents,
            uris=uris,
            data=data
        )
        
        print(f"Successfully migrated {len(ids)} items in collection {collection.name}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Normalize embeddings in a ChromaDB database")
    parser.add_argument("source", help="Path to source database")
    parser.add_argument("destination", help="Path to destination database (must not exist)")
    
    args = parser.parse_args()
    
    migrate_database(args.source, args.destination)
