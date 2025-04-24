#!/usr/bin/env python3
"""
embedder.py - Vector embedding generator for GameScout's knowledge base

This module converts processed text documents into vector embeddings that can be 
efficiently searched using semantic similarity. It's a critical component of 
the RAG (Retrieval-Augmented Generation) system, allowing the assistant to find
relevant game information based on natural language queries.

The embedding process:
1. Loads processed documents from JSON files
2. Uses a transformer model to create vector embeddings
3. Saves the embeddings and corresponding metadata for later retrieval

Usage:
    python embedder.py
"""

import os
import json
import logging
import numpy as np
from glob import glob
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("embedding.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Module constants
INPUT_DIR = "data/wiki_processed"
OUTPUT_DIR = "vector_db"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Lightweight but effective embedding model
BATCH_SIZE = 32  # Process documents in batches to manage memory usage

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_documents():
    """
    Load processed documents from JSON files.
    
    Reads all JSON files in the input directory, validating that each has
    the required fields before adding to the document collection.
    
    Returns:
        list: Collection of document dictionaries with metadata
              Empty list if no valid documents are found
    """
    documents = []
    json_files = glob(os.path.join(INPUT_DIR, "*.json"))
    
    if not json_files:
        logger.warning(f"No JSON files found in {INPUT_DIR}. Run scraper.py first.")
        return []
    
    logger.info(f"Loading {len(json_files)} documents...")
    
    for file_path in tqdm(json_files, desc="Loading documents"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                doc = json.load(f)
                
                # Validate required fields
                required_fields = ["title", "content", "url", "tags"]
                if not all(field in doc for field in required_fields):
                    logger.warning(f"Document missing required fields: {file_path}")
                    continue
                
                # Add document metadata
                doc["file_path"] = file_path
                doc["document_id"] = os.path.basename(file_path).rsplit('.', 1)[0]
                
                documents.append(doc)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in {file_path}")
        except Exception as e:
            logger.error(f"Error loading {file_path}: {str(e)}")
    
    logger.info(f"Successfully loaded {len(documents)} documents")
    return documents


def create_embeddings(documents):
    """
    Create vector embeddings for all documents.
    
    Uses the Sentence Transformers library to encode document content into
    dense vector representations that capture semantic meaning.
    
    Args:
        documents (list): Collection of document dictionaries to embed
        
    Returns:
        tuple: (embeddings_array, metadata)
               - embeddings_array: NumPy array of document embeddings
               - metadata: List of document metadata dictionaries
               Returns (None, None) if no valid documents to embed
    """
    if not documents:
        logger.warning("No documents to embed")
        return None, None
    
    # Combine title and content for better semantic representation
    texts = [f"{doc['title']}\n\n{doc['content']}" for doc in documents]
    metadata = [{
        "document_id": doc["document_id"],
        "title": doc["title"],
        "url": doc["url"],
        "tags": doc["tags"],
        "file_path": doc["file_path"]
    } for doc in documents]
    
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)
    
    logger.info(f"Generating embeddings for {len(texts)} documents...")
    embeddings = []
    
    # Process in batches to manage memory usage
    for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="Embedding batches"):
        batch_texts = texts[i:i+BATCH_SIZE]
        batch_embeddings = model.encode(batch_texts, show_progress_bar=False)
        embeddings.extend(batch_embeddings)
    
    embeddings_array = np.array(embeddings).astype('float32')
    
    # Log embedding statistics
    embedding_dim = embeddings_array.shape[1]
    logger.info(f"Created embeddings with dimension: {embedding_dim}")
    
    return embeddings_array, metadata


def save_embeddings(embeddings, metadata):
    """
    Save embeddings and metadata to persistent storage.
    
    Stores the embedding vectors as a NumPy array and the corresponding
    metadata as a JSON file for later retrieval.
    
    Args:
        embeddings (ndarray): NumPy array of document embeddings
        metadata (list): List of metadata dictionaries
    """
    if embeddings is None or not metadata:
        logger.warning("No embeddings or metadata to save")
        return
    
    # Save embeddings as NumPy array for efficient loading
    embeddings_path = os.path.join(OUTPUT_DIR, "embeddings.npy")
    np.save(embeddings_path, embeddings)
    
    # Save metadata as JSON for human readability
    metadata_path = os.path.join(OUTPUT_DIR, "metadata.json")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved {len(embeddings)} embeddings to {embeddings_path}")
    logger.info(f"Saved metadata to {metadata_path}")


def main():
    """
    Main function to orchestrate the document embedding process.
    
    Executes the full pipeline:
    1. Loading documents
    2. Creating embeddings
    3. Saving results to disk
    """
    logger.info("Starting document embedding process")
    
    # Load documents
    documents = load_documents()
    if not documents:
        logger.warning("No documents found to embed. Exiting.")
        return
    
    # Create embeddings
    embeddings, metadata = create_embeddings(documents)
    if embeddings is None:
        logger.warning("Failed to create embeddings. Exiting.")
        return
    
    # Save embeddings and metadata
    save_embeddings(embeddings, metadata)
    
    logger.info("Document embedding completed successfully")


if __name__ == "__main__":
    main()