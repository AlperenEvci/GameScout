#!/usr/bin/env python3
# indexer.py - Creates and saves a FAISS index from document embeddings

import os
import json
import pickle
import logging
import numpy as np
import faiss
from time import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("indexing.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# FAISS için log seviyesini düzenle (GPU hata mesajını gizlemek için)
logging.getLogger('faiss').setLevel(logging.ERROR)

# Constants
VECTOR_DB_DIR = "vector_db"
EMBEDDINGS_FILE = os.path.join(VECTOR_DB_DIR, "embeddings.npy")
METADATA_FILE = os.path.join(VECTOR_DB_DIR, "metadata.json")
FAISS_INDEX_FILE = os.path.join(VECTOR_DB_DIR, "bg3_knowledge.faiss")
FAISS_METADATA_FILE = os.path.join(VECTOR_DB_DIR, "bg3_knowledge_metadata.pkl")


def load_embeddings():
    """Load embeddings and metadata from files."""
    if not os.path.exists(EMBEDDINGS_FILE):
        logger.error(f"Embeddings file not found: {EMBEDDINGS_FILE}")
        logger.error("Run embedder.py first!")
        return None, None
        
    if not os.path.exists(METADATA_FILE):
        logger.error(f"Metadata file not found: {METADATA_FILE}")
        logger.error("Run embedder.py first!")
        return None, None
        
    try:
        # Load embeddings
        embeddings = np.load(EMBEDDINGS_FILE)
        logger.info(f"Loaded embeddings with shape: {embeddings.shape}")
        
        # Load metadata
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        logger.info(f"Loaded metadata for {len(metadata)} documents")
        
        # Verify dimensions match
        if len(metadata) != embeddings.shape[0]:
            logger.warning(f"Mismatch between embeddings ({embeddings.shape[0]}) and metadata ({len(metadata)})")
        
        return embeddings, metadata
        
    except Exception as e:
        logger.error(f"Error loading embeddings or metadata: {str(e)}")
        return None, None


def build_faiss_index(embeddings):
    """Build a FAISS index from embeddings."""
    if embeddings is None:
        return None
    
    # Get dimensions
    n_vectors, dimension = embeddings.shape
    logger.info(f"Building FAISS index with {n_vectors} vectors of dimension {dimension}")
    
    try:
        # Create a flat L2 index (exact nearest neighbor search)
        index = faiss.IndexFlatL2(dimension)
        
        # Add embeddings to the index
        start_time = time()
        index.add(embeddings)
        index_time = time() - start_time
        
        logger.info(f"FAISS index built in {index_time:.2f}s with {index.ntotal} vectors")
        
        # Basic quality check
        if index.ntotal != n_vectors:
            logger.warning(f"Index contains {index.ntotal} vectors, expected {n_vectors}")
            
        return index
    
    except Exception as e:
        logger.error(f"Error building FAISS index: {str(e)}")
        return None


def save_faiss_index(index, metadata):
    """Save FAISS index and metadata to files."""
    if index is None or metadata is None:
        logger.warning("No index or metadata to save")
        return False
    
    try:
        # Save FAISS index
        start_time = time()
        faiss.write_index(index, FAISS_INDEX_FILE)
        index_save_time = time() - start_time
        logger.info(f"FAISS index saved to {FAISS_INDEX_FILE} in {index_save_time:.2f}s")
        
        # Save metadata
        with open(FAISS_METADATA_FILE, 'wb') as f:
            pickle.dump(metadata, f)
        logger.info(f"Metadata saved to {FAISS_METADATA_FILE}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error saving FAISS index or metadata: {str(e)}")
        return False


def main():
    """Main function to build and save a FAISS index."""
    logger.info("Starting FAISS indexing process")
    
    # Load embeddings and metadata
    embeddings, metadata = load_embeddings()
    if embeddings is None or metadata is None:
        return
    
    # Build FAISS index
    index = build_faiss_index(embeddings)
    if index is None:
        return
    
    # Save FAISS index and metadata
    success = save_faiss_index(index, metadata)
    
    if success:
        logger.info("FAISS indexing completed successfully")
    else:
        logger.error("FAISS indexing failed")


if __name__ == "__main__":
    main()