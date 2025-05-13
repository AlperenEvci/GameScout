#!/usr/bin/env python3
"""
retrain_rag.py - Script to retrain and optimize the RAG system

This script provides an easy way to rebuild the knowledge base with the latest
documents and improved embedding techniques. It also offers various options
for optimizing the RAG components.

Usage:
    python retrain_rag.py [--rebuild-all] [--optimize-index] [--update-model] [--test]
"""

import os
import argparse
import logging
from pathlib import Path
import sys
import time
import json
from tqdm import tqdm

# Add project root to path for imports
sys.path.append(str(Path(__file__).parent))

# Import project modules
from embedder import create_embeddings, load_documents, save_embeddings
from indexer import load_embeddings, build_faiss_index, save_faiss_index
from agent.rag import RAGAssistant
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("rag_retraining.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
VECTOR_DB_DIR = "vector_db"
INPUT_DIR = "data/wiki_processed"
TEST_QUESTIONS = [
    "Who is Shadowheart?",
    "What quests can I find in Emerald Grove?",
    "How does the combat system work in Baldur's Gate 3?",
    "Tell me about the different classes in BG3",
    "What are the best weapons for a Paladin?"
]


def rebuild_knowledge_base(update_model=False):
    """
    Rebuild the knowledge base from scratch.
    
    This process:
    1. Loads documents from the processed wiki files
    2. Creates new embeddings with the latest model
    3. Builds a new FAISS index
    4. Saves everything to the vector_db directory
    
    Args:
        update_model (bool): Whether to use a newer embedding model
    
    Returns:
        bool: Success status
    """
    logger.info("Starting knowledge base rebuild process...")
    
    # Check if input directory exists
    if not os.path.exists(INPUT_DIR):
        logger.error(f"Input directory not found: {INPUT_DIR}")
        return False
    
    # Create vector_db directory if it doesn't exist
    os.makedirs(VECTOR_DB_DIR, exist_ok=True)
    
    # Step 1: Load documents
    logger.info("Loading documents...")
    documents = load_documents()
    if not documents:
        logger.error("No documents found to embed.")
        return False
    logger.info(f"Loaded {len(documents)} documents.")
    
    # Step 2: Create embeddings
    logger.info("Creating embeddings...")
    embeddings, metadata = create_embeddings(documents)
    if embeddings is None:
        logger.error("Failed to create embeddings.")
        return False
    logger.info(f"Created embeddings with shape {embeddings.shape}")
    
    # Step 3: Save embeddings and metadata
    logger.info("Saving embeddings and metadata...")
    save_embeddings(embeddings, metadata)
    
    # Step 4: Build FAISS index
    logger.info("Building FAISS index...")
    index = build_faiss_index(embeddings)
    if index is None:
        logger.error("Failed to build FAISS index.")
        return False
    
    # Step 5: Save FAISS index
    logger.info("Saving FAISS index...")
    save_faiss_index(index, metadata)
    
    logger.info("Knowledge base rebuild completed successfully!")
    return True


def optimize_index():
    """
    Optimize the existing FAISS index for better performance.
    
    This includes:
    - Converting to a more efficient index type (IVF)
    - Training the index for better clustering
    - Adding the vectors again to the optimized index
    
    Returns:
        bool: Success status
    """
    import faiss
    
    logger.info("Optimizing FAISS index...")
    
    try:
        # Load the existing embeddings and metadata
        embeddings, metadata = load_embeddings()
        if embeddings is None:
            logger.error("Failed to load embeddings.")
            return False
        
        # Get dimensions
        n_vectors, dimension = embeddings.shape
        logger.info(f"Optimizing index with {n_vectors} vectors of dimension {dimension}")
        
        # Only optimize if we have enough vectors
        if n_vectors < 1000:
            logger.info("Not enough vectors for significant optimization. Skipping.")
            return True
        
        # Create an IVF index with better search characteristics
        # The nlist parameter controls how many clusters to use - sqrt(n) is a good starting point
        nlist = int(min(4096, 4 * (n_vectors**0.5)))
        quantizer = faiss.IndexFlatL2(dimension)
        index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
        
        # Train the index with our vectors
        logger.info(f"Training IVF index with {nlist} clusters...")
        index.train(embeddings)
        
        # Add the vectors
        index.add(embeddings)
        
        # Set search parameters
        index.nprobe = min(64, nlist // 4)  # How many clusters to visit during search
        
        # Save the optimized index
        logger.info("Saving optimized index...")
        faiss.write_index(index, os.path.join(VECTOR_DB_DIR, "bg3_knowledge.faiss"))
        
        logger.info("Index optimization completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error optimizing index: {str(e)}")
        return False


def test_rag_system():
    """
    Test the RAG system with a few sample questions.
    
    Returns:
        bool: Success status
    """
    logger.info("Testing RAG system with sample questions...")
    
    # Initialize RAG assistant
    assistant = RAGAssistant()
    if not assistant.initialize():
        logger.error("Failed to initialize RAG assistant.")
        return False
    
    # Test with sample questions
    results = []
    for question in tqdm(TEST_QUESTIONS, desc="Testing questions"):
        try:
            logger.info(f"Q: {question}")
            response = assistant.ask_game_ai(question)
            logger.info(f"A: {response}")
            
            results.append({
                "question": question,
                "answer": response,
                "time": time.time()
            })
            
            # Wait a bit to avoid rate limiting
            time.sleep(3)
            
        except Exception as e:
            logger.error(f"Error testing question '{question}': {str(e)}")
    
    # Save test results
    with open("rag_test_results.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.info("RAG system testing completed. Results saved to rag_test_results.json")
    assistant.shutdown()
    return True


def main():
    """Main function to process command line arguments and execute requested actions"""
    parser = argparse.ArgumentParser(description="Retrain and optimize the RAG system")
    parser.add_argument("--rebuild-all", action="store_true", help="Rebuild the knowledge base from scratch")
    parser.add_argument("--optimize-index", action="store_true", help="Optimize the FAISS index")
    parser.add_argument("--update-model", action="store_true", help="Use a newer embedding model")
    parser.add_argument("--test", action="store_true", help="Test the RAG system with sample questions")
    
    args = parser.parse_args()
    
    # Default behavior if no arguments provided
    if not (args.rebuild_all or args.optimize_index or args.test):
        args.rebuild_all = True  # Default action
        logger.info("No specific action requested. Defaulting to rebuilding knowledge base.")
    
    success = True
    
    # Rebuild knowledge base if requested
    if args.rebuild_all:
        success = success and rebuild_knowledge_base(update_model=args.update_model)
    
    # Optimize the index if requested
    if args.optimize_index:
        success = success and optimize_index()
    
    # Test the RAG system if requested
    if args.test:
        success = success and test_rag_system()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())