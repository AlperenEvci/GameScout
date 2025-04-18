#!/usr/bin/env python3
# embedder.py - Embeds processed documents into vector representations

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

# Constants
INPUT_DIR = "data/wiki_processed"
OUTPUT_DIR = "vector_db"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # A lightweight but effective model
BATCH_SIZE = 32

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_documents():
    """Load all processed documents from JSON files."""
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
                
                # Ensure the document has required fields
                if not all(k in doc for k in ["title", "content", "url", "tags"]):
                    logger.warning(f"Document missing required fields: {file_path}")
                    continue
                
                # Add document metadata
                doc["file_path"] = file_path
                doc["document_id"] = os.path.basename(file_path).rsplit('.', 1)[0]
                
                documents.append(doc)
        except Exception as e:
            logger.error(f"Error loading {file_path}: {str(e)}")
    
    logger.info(f"Loaded {len(documents)} documents successfully")
    return documents


def create_embeddings(documents):
    """Create embeddings for all documents using Sentence Transformers."""
    if not documents:
        logger.warning("No documents to embed")
        return None, None
    
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
    
    # Process in batches to avoid memory issues
    for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="Embedding batches"):
        batch_texts = texts[i:i+BATCH_SIZE]
        batch_embeddings = model.encode(batch_texts, show_progress_bar=False)
        embeddings.extend(batch_embeddings)
    
    embeddings_array = np.array(embeddings).astype('float32')
    
    # Basic embedding statistics
    embedding_dim = embeddings_array.shape[1]
    logger.info(f"Embeddings created with dimension: {embedding_dim}")
    
    return embeddings_array, metadata


def save_embeddings(embeddings, metadata):
    """Save embeddings and metadata to files."""
    if embeddings is None or not metadata:
        logger.warning("No embeddings or metadata to save")
        return
    
    # Save embeddings as numpy array
    embeddings_path = os.path.join(OUTPUT_DIR, "embeddings.npy")
    np.save(embeddings_path, embeddings)
    
    # Save metadata as JSON
    metadata_path = os.path.join(OUTPUT_DIR, "metadata.json")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved {len(embeddings)} embeddings to {embeddings_path}")
    logger.info(f"Saved metadata to {metadata_path}")


def main():
    """Main function to process documents and create embeddings."""
    logger.info("Starting document embedding process")
    
    # Load documents
    documents = load_documents()
    if not documents:
        return
    
    # Create embeddings
    embeddings, metadata = create_embeddings(documents)
    if embeddings is None:
        return
    
    # Save embeddings and metadata
    save_embeddings(embeddings, metadata)
    
    logger.info("Document embedding completed successfully")


if __name__ == "__main__":
    main()