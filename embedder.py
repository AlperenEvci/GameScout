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
# Updated to newer, more powerful embedding model with better semantic understanding
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"  # Better semantic understanding than MiniLM
BATCH_SIZE = 32  # Process documents in batches to manage memory usage
CHUNK_SIZE = 512  # Size for document chunking
CHUNK_OVERLAP = 128  # Overlap between chunks to maintain context

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


def chunk_document(doc, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
    """
    Split a document into smaller chunks for more precise retrieval.
    
    Args:
        doc (dict): Document dictionary with content to chunk
        chunk_size (int): Target size of each chunk
        chunk_overlap (int): Overlap between consecutive chunks
    
    Returns:
        list: List of document chunks with updated metadata
    """
    title = doc["title"]
    content = doc["content"]
    doc_id = doc["document_id"]
    
    # Short document, no need to chunk
    if len(content) <= chunk_size:
        return [{
            "document_id": f"{doc_id}-chunk-0",
            "parent_id": doc_id,
            "title": title,
            "url": doc["url"],
            "tags": doc["tags"],
            "file_path": doc["file_path"],
            "content": content,
            "chunk_index": 0
        }]
    
    # Split content into chunks with overlap
    chunks = []
    start = 0
    chunk_index = 0
    
    while start < len(content):
        # Calculate end position with respect to chunk size
        end = min(start + chunk_size, len(content))
        
        # If not the first chunk and not the last chunk, adjust start for overlap
        if start > 0:
            start = start - chunk_overlap
            end = min(start + chunk_size, len(content))
        
        # Extract chunk text
        chunk_text = content[start:end]
        
        # Create chunk metadata
        chunk = {
            "document_id": f"{doc_id}-chunk-{chunk_index}",
            "parent_id": doc_id,
            "title": f"{title} (Part {chunk_index+1})",
            "url": doc["url"],
            "tags": doc["tags"],
            "file_path": doc["file_path"],
            "content": chunk_text,
            "chunk_index": chunk_index
        }
        
        chunks.append(chunk)
        chunk_index += 1
        start = end
    
    logger.debug(f"Split document '{title}' into {len(chunks)} chunks")
    return chunks

def create_embeddings(documents):
    """
    Create vector embeddings for all documents.
    
    Uses the Sentence Transformers library to encode document content into
    dense vector representations that capture semantic meaning. Documents are
    first chunked for better retrieval precision.
    
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
    
    # Chunk documents for better retrieval granularity
    logger.info(f"Chunking {len(documents)} documents...")
    chunked_docs = []
    for doc in documents:
        chunks = chunk_document(doc)
        chunked_docs.extend(chunks)
    
    logger.info(f"Created {len(chunked_docs)} chunks from {len(documents)} documents")
    
    # Prepare text and metadata for embedding
    texts = [f"{doc['title']}\n\n{doc['content']}" for doc in chunked_docs]
    metadata = [{
        "document_id": doc["document_id"],
        "parent_id": doc.get("parent_id", doc["document_id"]),
        "title": doc["title"],
        "url": doc["url"],
        "tags": doc["tags"],
        "file_path": doc["file_path"],
        "chunk_index": doc.get("chunk_index", 0)
    } for doc in chunked_docs]
    
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