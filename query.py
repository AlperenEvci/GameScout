#!/usr/bin/env python3
# query.py - Query the FAISS vector database for relevant BG3 information

import os
import pickle
import logging
import argparse
# FAISS için log seviyesini düzenle (GPU hata mesajını gizlemek için)
logging.getLogger('faiss').setLevel(logging.ERROR)
import faiss
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
VECTOR_DB_DIR = "vector_db"
FAISS_INDEX_FILE = os.path.join(VECTOR_DB_DIR, "bg3_knowledge.faiss")
FAISS_METADATA_FILE = os.path.join(VECTOR_DB_DIR, "bg3_knowledge_metadata.pkl")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# GPU kullanımını kontrol et
def try_use_faiss_gpu():
    """FAISS GPU sürümünün kullanılabilir olup olmadığını kontrol et ve sessizce başarısız ol"""
    try:
        # GPU desteği varsa kullan
        res = faiss.StandardGpuResources()
        return res
    except (ImportError, AttributeError):
        # GPU desteği yoksa sessizce CPU'ya geri dön
        return None


class BG3KnowledgeBase:
    """Baldur's Gate 3 knowledge retrieval system using vector similarity search."""
    
    def __init__(self):
        self.index = None
        self.metadata = None
        self.model = None
        self.is_initialized = False
    
    def initialize(self):
        """Load the FAISS index, metadata, and embedding model."""
        try:
            # Check if files exist
            if not os.path.exists(FAISS_INDEX_FILE) or not os.path.exists(FAISS_METADATA_FILE):
                logger.error(f"FAISS index or metadata file not found. Run indexer.py first!")
                return False
            
            # Load FAISS index
            logger.info(f"Loading FAISS index from {FAISS_INDEX_FILE}")
            self.index = faiss.read_index(FAISS_INDEX_FILE)
            
            # Load metadata
            logger.info(f"Loading metadata from {FAISS_METADATA_FILE}")
            with open(FAISS_METADATA_FILE, 'rb') as f:
                self.metadata = pickle.load(f)
            
            # Load embedding model
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
            self.model = SentenceTransformer(EMBEDDING_MODEL)
            
            # Verify index is populated
            if self.index.ntotal == 0:
                logger.error("FAISS index is empty")
                return False
                
            logger.info(f"Knowledge base initialized with {self.index.ntotal} documents")
            self.is_initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize knowledge base: {str(e)}")
            return False
    
    def search(self, query, top_k=3):
        """Search for documents relevant to the query."""
        if not self.is_initialized:
            logger.error("Knowledge base not initialized. Call initialize() first.")
            return []
        
        try:
            # Embed the query
            query_embedding = self.model.encode([query])[0].reshape(1, -1).astype('float32')
            
            # Search the index
            distances, indices = self.index.search(query_embedding, top_k)
            
            # Get the metadata for the results
            results = []
            for i, idx in enumerate(indices[0]):
                if idx != -1:  # -1 means no valid result
                    metadata = self.metadata[idx]
                    results.append({
                        "title": metadata["title"],
                        "url": metadata["url"],
                        "distance": distances[0][i],
                        "content": self._get_content(metadata["file_path"]),
                        "tags": metadata.get("tags", [])
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching knowledge base: {str(e)}")
            return []
    
    def _get_content(self, file_path):
        """Get the content from the original file."""
        try:
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("content", "")
        except Exception as e:
            logger.error(f"Error loading content from {file_path}: {str(e)}")
            return ""


def format_result(result, snippet_length=300):
    """Format a search result for display."""
    content = result["content"]
    if len(content) > snippet_length:
        content = content[:snippet_length] + "..."
    
    return (
        f"{'=' * 60}\n"
        f"TITLE: {result['title']}\n"
        f"RELEVANCE: {1.0 / (1.0 + result['distance']):.2f}\n"
        f"TAGS: {', '.join(result['tags'])}\n"
        f"URL: {result['url']}\n"
        f"{'-' * 40}\n"
        f"CONTENT: {content}\n"
    )


def main():
    """Main function for command line interface."""
    parser = argparse.ArgumentParser(description="Query the Baldur's Gate 3 knowledge base")
    parser.add_argument("query", help="The search query", nargs="?")
    parser.add_argument("--top-k", type=int, default=3, help="Number of results to return")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    args = parser.parse_args()
    
    # Initialize knowledge base
    kb = BG3KnowledgeBase()
    if not kb.initialize():
        return
    
    # Interactive mode
    if args.interactive:
        print("\n" + "=" * 60)
        print("Baldur's Gate 3 Knowledge Base Interactive Mode")
        print("Type 'exit', 'quit', or Ctrl+C to quit")
        print("=" * 60 + "\n")
        
        try:
            while True:
                query = input("\nEnter your query: ")
                if query.lower() in ['exit', 'quit']:
                    break
                
                if not query.strip():
                    continue
                    
                results = kb.search(query, args.top_k)
                
                if not results:
                    print("No results found.")
                    continue
                
                print(f"\nFound {len(results)} results:\n")
                for i, result in enumerate(results, 1):
                    print(format_result(result))
        
        except KeyboardInterrupt:
            print("\nExiting...")
    
    # Single query mode
    elif args.query:
        results = kb.search(args.query, args.top_k)
        
        if not results:
            print("No results found.")
            return
            
        print(f"\nFound {len(results)} results for '{args.query}':\n")
        for i, result in enumerate(results, 1):
            print(format_result(result))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()