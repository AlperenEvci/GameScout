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
    """Baldur's Gate 3 knowledge retrieval system using advanced vector similarity search."""
    
    def __init__(self):
        self.index = None
        self.metadata = None
        self.model = None
        self.is_initialized = False
        # Memory cache for recent queries to improve response time
        self.query_cache = {}
        self.max_cache_size = 100
        
        # Try to use GPU if available
        self.gpu_resources = try_use_faiss_gpu()
    
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
            
            # Use GPU if available
            if self.gpu_resources:
                logger.info("Using GPU for vector search")
                self.index = faiss.index_cpu_to_gpu(self.gpu_resources, 0, self.index)
            
            # Load metadata
            logger.info(f"Loading metadata from {FAISS_METADATA_FILE}")
            with open(FAISS_METADATA_FILE, 'rb') as f:
                self.metadata = pickle.load(f)
            
            # Load embedding model - update the model to match what's used in embedder.py
            # Using the same improved model as in embedder.py
            embedding_model = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
            logger.info(f"Loading embedding model: {embedding_model}")
            self.model = SentenceTransformer(embedding_model)
            
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
    def _keyword_search(self, query, metadata, top_k=10):
        """
        Perform a simple keyword-based search on document content.
        
        Args:
            query (str): Search query
            metadata (list): Metadata entries to search through
            top_k (int): Maximum number of results to return
            
        Returns:
            list: Matching document indices
        """
        import re
        from collections import Counter
        
        # Normalize and tokenize query
        query_terms = set(re.findall(r'\w+', query.lower()))
        if not query_terms:
            return []
            
        # Score documents by term frequency
        scores = []
        for idx, meta in enumerate(self.metadata):
            # Get content
            content = self._get_content(meta["file_path"]).lower()
            title = meta["title"].lower()
            
            # Count matching terms in content and title (weighted)
            content_matches = sum(1 for term in query_terms if term in content)
            title_matches = sum(3 for term in query_terms if term in title)  # Title matches weighted higher
            
            total_score = content_matches + title_matches
            if total_score > 0:
                scores.append((idx, total_score))
        
        # Sort by score and return indices
        scores.sort(key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in scores[:top_k]]
        
    def _rerank_results(self, query, results, diversity_factor=0.5):
        """
        Rerank results to improve relevance and diversity.
        
        Args:
            query (str): Original query
            results (list): Initial search results
            diversity_factor (float): How much to emphasize diversity vs similarity
            
        Returns:
            list: Reranked results
        """
        if len(results) <= 1:
            return results
            
        # Extract unique parent documents to reduce redundancy
        seen_parents = set()
        diverse_results = []
        
        for result in results:
            parent_id = result.get("parent_id", result["document_id"])
            
            # If we haven't seen this parent document, prioritize it
            if parent_id not in seen_parents:
                result["score"] = result["score"] * (1.0 + diversity_factor)
                seen_parents.add(parent_id)
                
            diverse_results.append(result)
            
        # Sort by adjusted score
        diverse_results.sort(key=lambda x: x["score"], reverse=True)
        return diverse_results
    
    def search(self, query, top_k=3):
        """
        Search for documents relevant to the query using hybrid search.
        
        This implements a hybrid search approach combining:
        1. Dense retrieval (vector similarity)
        2. Sparse/keyword retrieval
        3. Result reranking and deduplication
        
        Args:
            query (str): Search query
            top_k (int): Maximum number of results to return
            
        Returns:
            list: Relevant documents with metadata
        """
        if not self.is_initialized:
            logger.error("Knowledge base not initialized. Call initialize() first.")
            return []
        
        # Check cache first
        cache_key = f"{query}:{top_k}"
        if cache_key in self.query_cache:
            logger.debug(f"Cache hit for query: {query}")
            return self.query_cache[cache_key]
        
        try:
            # Get more candidates for reranking
            search_k = min(top_k * 3, self.index.ntotal)
            
            # 1. Dense retrieval with vector similarity
            query_embedding = self.model.encode([query])[0].reshape(1, -1).astype('float32')
            dense_distances, dense_indices = self.index.search(query_embedding, search_k)
            
            # 2. Sparse/keyword retrieval
            keyword_indices = self._keyword_search(query, self.metadata, search_k)
            
            # Combine results (unique indices)
            all_indices = list(set([idx for idx in dense_indices[0] if idx != -1] + keyword_indices))
            
            # Get combined results with scores
            results = []
            for idx in all_indices:
                metadata = self.metadata[idx]
                
                # Find corresponding distance if available from vector search
                try:
                    dist_idx = dense_indices[0].tolist().index(idx)
                    distance = dense_distances[0][dist_idx]
                except ValueError:
                    # Wasn't in the vector results, assign a default score
                    distance = 1.0
                
                # Convert distance to score (lower distance = higher score)
                score = 1.0 / (1.0 + distance)
                
                result = {
                    "title": metadata["title"],
                    "url": metadata["url"],
                    "distance": distance,
                    "score": score,
                    "content": self._get_content(metadata["file_path"]),
                    "tags": metadata.get("tags", []),
                    "parent_id": metadata.get("parent_id", metadata["document_id"])
                }
                results.append(result)
            
            # 3. Rerank results for better relevance and diversity
            reranked_results = self._rerank_results(query, results)
            final_results = reranked_results[:top_k]
            
            # Update cache
            if len(self.query_cache) >= self.max_cache_size:
                # Remove a random item to prevent cache from growing too large
                self.query_cache.pop(next(iter(self.query_cache)))
            self.query_cache[cache_key] = final_results
            
            return final_results
            
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