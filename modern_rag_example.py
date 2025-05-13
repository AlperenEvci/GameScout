#!/usr/bin/env python3
"""
modern_rag_example.py - Example implementation of a state-of-the-art RAG system

This script demonstrates how to build a modern Retrieval-Augmented Generation
system from scratch, including all the key components and latest best practices.

Note: This is an educational example that you can adapt to your specific needs.
"""

import os
import sys
import time
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ----- 1. DATA PREPARATION MODULE -----

class DocumentProcessor:
    """Process raw documents into chunks suitable for embedding."""
    
    def __init__(self, chunk_size=512, chunk_overlap=128):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def load_documents(self, directory: str) -> List[Dict[str, Any]]:
        """Load documents from a directory of JSON files."""
        documents = []
        try:
            import glob
            json_files = glob.glob(os.path.join(directory, "*.json"))
            
            if not json_files:
                logger.warning(f"No JSON files found in {directory}")
                return []
            
            logger.info(f"Loading {len(json_files)} documents...")
            
            for file_path in json_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        doc = json.load(f)
                        
                        # Add document metadata
                        doc["file_path"] = file_path
                        doc["document_id"] = os.path.basename(file_path).split('.')[0]
                        
                        documents.append(doc)
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {str(e)}")
            
            logger.info(f"Successfully loaded {len(documents)} documents")
            return documents
            
        except Exception as e:
            logger.error(f"Error in document loading: {str(e)}")
            return []
    
    def chunk_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Split documents into chunks with overlap."""
        chunks = []
        
        for doc in documents:
            doc_chunks = self._chunk_document(doc)
            chunks.extend(doc_chunks)
        
        logger.info(f"Created {len(chunks)} chunks from {len(documents)} documents")
        return chunks
    
    def _chunk_document(self, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Split a single document into chunks."""
        title = doc["title"]
        content = doc["content"]
        doc_id = doc["document_id"]
        
        # If content is short, keep as single chunk
        if len(content) <= self.chunk_size:
            return [{
                **doc,
                "chunk_id": f"{doc_id}-0",
                "parent_id": doc_id,
                "chunk_index": 0
            }]
        
        # Split content into chunks
        doc_chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(content):
            # Calculate end with respect to chunk size
            end = min(start + self.chunk_size, len(content))
            
            # Handle overlap for all chunks except the first one
            if start > 0:
                start = start - self.chunk_overlap
                end = min(start + self.chunk_size, len(content))
            
            chunk_text = content[start:end]
            
            # Create chunk with metadata
            chunk = {
                **doc,  # Copy all original fields
                "content": chunk_text,
                "chunk_id": f"{doc_id}-{chunk_index}",
                "parent_id": doc_id,
                "title": f"{title} (Part {chunk_index+1})",
                "chunk_index": chunk_index
            }
            
            doc_chunks.append(chunk)
            chunk_index += 1
            start = end
        
        return doc_chunks


# ----- 2. EMBEDDING MODULE -----

class EmbeddingEngine:
    """Generate and manage vector embeddings for text chunks."""
    
    def __init__(self, model_name="BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self.model = None
    
    def initialize(self) -> bool:
        """Load the embedding model."""
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            return True
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {str(e)}")
            return False
    
    def embed_documents(self, chunks: List[Dict[str, Any]], batch_size=32) -> Tuple[np.ndarray, List[Dict]]:
        """Generate embeddings for document chunks."""
        if not self.model:
            logger.error("Embedding model not initialized")
            return None, None
        
        try:
            # Prepare text for embedding
            texts = [f"{chunk['title']}\n\n{chunk['content']}" for chunk in chunks]
            metadata = chunks
            
            # Process in batches
            logger.info(f"Generating embeddings for {len(texts)} chunks...")
            embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i+batch_size]
                batch_embeddings = self.model.encode(batch_texts, show_progress_bar=False)
                embeddings.extend(batch_embeddings)
            
            # Convert to numpy array
            embeddings_array = np.array(embeddings).astype('float32')
            
            logger.info(f"Created embeddings with dimension: {embeddings_array.shape}")
            return embeddings_array, metadata
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            return None, None
    
    def embed_query(self, query: str) -> np.ndarray:
        """Generate embedding for a search query."""
        if not self.model:
            logger.error("Embedding model not initialized")
            return None
        
        try:
            query_embedding = self.model.encode([query])[0].astype('float32')
            return query_embedding
        except Exception as e:
            logger.error(f"Error embedding query: {str(e)}")
            return None


# ----- 3. VECTOR DATABASE MODULE -----

class VectorStore:
    """Store and search vector embeddings."""
    
    def __init__(self, index_path="vector_db/knowledge.faiss", metadata_path="vector_db/metadata.json"):
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.index = None
        self.metadata = []
    
    def initialize(self) -> bool:
        """Load existing index if available."""
        try:
            import faiss
            
            # Check if index file exists
            if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
                # Load FAISS index
                logger.info(f"Loading index from {self.index_path}")
                self.index = faiss.read_index(self.index_path)
                
                # Load metadata
                logger.info(f"Loading metadata from {self.metadata_path}")
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
                
                logger.info(f"Vector store initialized with {self.index.ntotal} vectors")
                return True
            else:
                logger.warning("Vector store files not found, will need to be created")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing vector store: {str(e)}")
            return False
    
    def create_index(self, embeddings: np.ndarray, metadata: List[Dict]) -> bool:
        """Create a new FAISS index."""
        try:
            import faiss
            
            # Get dimensions
            n_vectors, dimension = embeddings.shape
            logger.info(f"Creating new index with {n_vectors} vectors of dimension {dimension}")
            
            # Create appropriate index based on size
            if n_vectors < 1000:
                # For small datasets, use exact search
                self.index = faiss.IndexFlatL2(dimension)
            else:
                # For larger datasets, use IVF for better performance
                nlist = int(min(4096, 4 * np.sqrt(n_vectors)))
                quantizer = faiss.IndexFlatL2(dimension)
                self.index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
                self.index.train(embeddings)
            
            # Add vectors to the index
            self.index.add(embeddings)
            
            # Store metadata
            self.metadata = metadata
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            
            # Save to disk
            faiss.write_index(self.index, self.index_path)
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Created and saved index with {self.index.ntotal} vectors")
            return True
            
        except Exception as e:
            logger.error(f"Error creating index: {str(e)}")
            return False
    
    def search(self, query_embedding: np.ndarray, top_k=5) -> List[Dict[str, Any]]:
        """Search the index for similar vectors."""
        if self.index is None:
            logger.error("Vector store not initialized")
            return []
        
        try:
            # Search the index
            query_embedding = query_embedding.reshape(1, -1)
            distances, indices = self.index.search(query_embedding, top_k)
            
            # Get metadata for results
            results = []
            for i, idx in enumerate(indices[0]):
                if idx != -1:  # -1 means no valid result
                    metadata = self.metadata[idx]
                    score = 1.0 / (1.0 + distances[0][i])  # Convert distance to similarity score
                    
                    result = {
                        **metadata,  # Include all metadata
                        "distance": distances[0][i],
                        "score": score
                    }
                    results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching vector store: {str(e)}")
            return []


# ----- 4. HYBRID SEARCH MODULE -----

class HybridSearchEngine:
    """Combine vector search with keyword search for better results."""
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.embedding_engine = None
    
    def set_embedding_engine(self, embedding_engine: EmbeddingEngine):
        """Set the embedding engine for vector search."""
        self.embedding_engine = embedding_engine
    
    def _keyword_search(self, query: str, top_k=10) -> List[Dict[str, Any]]:
        """Simple keyword search across all metadata."""
        import re
        from collections import Counter
        
        # Break query into keywords
        query_terms = set(re.findall(r'\w+', query.lower()))
        if not query_terms:
            return []
        
        # Score documents by matching terms
        scores = []
        for idx, meta in enumerate(self.vector_store.metadata):
            # Score by title and content
            title = meta.get("title", "").lower()
            content = meta.get("content", "").lower()
            
            title_matches = sum(3 for term in query_terms if term in title)  # Weight title matches higher
            content_matches = sum(1 for term in query_terms if term in content)
            
            score = title_matches + content_matches
            if score > 0:
                scores.append((idx, score))
        
        # Sort by score and get top matches
        scores.sort(key=lambda x: x[1], reverse=True)
        top_indices = [idx for idx, _ in scores[:top_k]]
        
        # Get metadata for results
        results = []
        for idx in top_indices:
            metadata = self.vector_store.metadata[idx]
            results.append({
                **metadata,
                "score": 0.5,  # Base score for keyword matches
                "distance": 1.0,
                "match_type": "keyword" 
            })
        
        return results
    
    def search(self, query: str, top_k=5) -> List[Dict[str, Any]]:
        """Perform hybrid search using both vector and keyword matching."""
        if not self.embedding_engine:
            logger.error("Embedding engine not set")
            return []
        
        try:
            # Get more results than needed for reranking
            search_k = min(top_k * 3, 20)
            
            # 1. Vector search
            query_embedding = self.embedding_engine.embed_query(query)
            if query_embedding is not None:
                vector_results = self.vector_store.search(query_embedding, search_k)
            else:
                vector_results = []
            
            # 2. Keyword search
            keyword_results = self._keyword_search(query, search_k)
            
            # 3. Combine results (remove duplicates by chunk_id)
            seen_ids = set()
            combined_results = []
            
            # First add vector results
            for result in vector_results:
                chunk_id = result.get("chunk_id", result.get("document_id"))
                if chunk_id not in seen_ids:
                    result["match_type"] = "vector"
                    combined_results.append(result)
                    seen_ids.add(chunk_id)
            
            # Then add keyword results if not already included
            for result in keyword_results:
                chunk_id = result.get("chunk_id", result.get("document_id"))
                if chunk_id not in seen_ids:
                    result["match_type"] = "keyword"
                    combined_results.append(result)
                    seen_ids.add(chunk_id)
            
            # 4. Rerank combined results
            reranked_results = self._rerank_results(query, combined_results)
            
            # Return top K results
            return reranked_results[:top_k]
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {str(e)}")
            return []
    
    def _rerank_results(self, query: str, results: List[Dict], diversity_factor=0.5) -> List[Dict]:
        """
        Rerank results for better relevance and diversity.
        
        Args:
            query: The original search query
            results: The combined search results
            diversity_factor: How much to emphasize diversity vs pure relevance
            
        Returns:
            List of reranked results
        """
        if len(results) <= 1:
            return results
        
        # 1. Extract parent documents to reduce redundancy
        seen_parents = set()
        diverse_results = []
        
        # 2. Boost score based on several factors
        for result in results:
            # Get parent document ID
            parent_id = result.get("parent_id", result.get("document_id"))
            
            # Base score (from vector or keyword search)
            score = result.get("score", 0.5)
            
            # Boost factors
            match_type_boost = 1.2 if result.get("match_type") == "vector" else 1.0
            title_match_boost = 1.5 if query.lower() in result.get("title", "").lower() else 1.0
            
            # Diversity boost (prioritize first occurrence of each parent document)
            diversity_boost = 1.0 + diversity_factor if parent_id not in seen_parents else 1.0
            seen_parents.add(parent_id)
            
            # Calculate final score
            final_score = score * match_type_boost * title_match_boost * diversity_boost
            result["final_score"] = final_score
            
            diverse_results.append(result)
        
        # Sort by final score
        diverse_results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        return diverse_results


# ----- 5. LLM INTERFACE MODULE -----

class LLMInterface:
    """Interface with Language Models to generate responses."""
    
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or "gpt-3.5-turbo"
        self.max_tokens = 500
        self.temperature = 0.7
        self.client = None
    
    def initialize(self) -> bool:
        """Initialize the LLM client."""
        try:
            # Try to import OpenAI client
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            logger.info(f"LLM interface initialized with model: {self.model}")
            return True
        except ImportError:
            logger.warning("OpenAI package not installed. Using mock responses.")
            return True
        except Exception as e:
            logger.error(f"Error initializing LLM interface: {str(e)}")
            return False
    
    def generate_response(self, prompt: str) -> str:
        """Generate a response from the LLM."""
        if not self.client:
            return self._mock_response(prompt)
        
        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant with expertise in Baldur's Gate 3."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {str(e)}")
            return "Sorry, I encountered an error while generating a response."
    
    def _mock_response(self, prompt: str) -> str:
        """Generate a mock response for testing without an LLM API."""
        return f"This is a simulated response to: '{prompt[:50]}...'"


# ----- 6. RAG SYSTEM MODULE -----

class RAGSystem:
    """Complete RAG system combining all components."""
    
    def __init__(self, 
                 data_dir="data/wiki_processed",
                 vector_db_dir="vector_db",
                 embedding_model="BAAI/bge-small-en-v1.5",
                 use_api_key=None):
        
        # Initialize components
        self.document_processor = DocumentProcessor(chunk_size=512, chunk_overlap=128)
        self.embedding_engine = EmbeddingEngine(model_name=embedding_model)
        
        # Set up file paths
        os.makedirs(vector_db_dir, exist_ok=True)
        self.index_path = os.path.join(vector_db_dir, "knowledge.faiss")
        self.metadata_path = os.path.join(vector_db_dir, "metadata.json")
        
        self.vector_store = VectorStore(self.index_path, self.metadata_path)
        self.search_engine = HybridSearchEngine(self.vector_store)
        self.llm_interface = LLMInterface(api_key=use_api_key)
        
        self.data_dir = data_dir
        self.is_initialized = False
        
        # Query cache to avoid repeated processing
        self.query_cache = {}
        self.cache_limit = 100
    
    def initialize(self) -> bool:
        """Initialize all components of the RAG system."""
        try:
            # 1. Initialize embedding engine
            if not self.embedding_engine.initialize():
                logger.error("Failed to initialize embedding engine")
                return False
            
            # 2. Connect embedding engine to search engine
            self.search_engine.set_embedding_engine(self.embedding_engine)
            
            # 3. Initialize vector store
            vector_store_ready = self.vector_store.initialize()
            
            # 4. If vector store doesn't exist, create it
            if not vector_store_ready:
                logger.info("Vector store not found, building from documents")
                self._build_knowledge_base()
            
            # 5. Initialize LLM interface
            if not self.llm_interface.initialize():
                logger.error("Failed to initialize LLM interface")
                return False
            
            self.is_initialized = True
            logger.info("RAG system successfully initialized")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing RAG system: {str(e)}")
            return False
    
    def _build_knowledge_base(self) -> bool:
        """Build the knowledge base from documents."""
        try:
            # 1. Load documents
            documents = self.document_processor.load_documents(self.data_dir)
            if not documents:
                logger.error(f"No documents found in {self.data_dir}")
                return False
            
            # 2. Chunk documents
            chunks = self.document_processor.chunk_documents(documents)
            
            # 3. Generate embeddings
            embeddings, metadata = self.embedding_engine.embed_documents(chunks)
            if embeddings is None:
                return False
            
            # 4. Create vector index
            success = self.vector_store.create_index(embeddings, metadata)
            return success
            
        except Exception as e:
            logger.error(f"Error building knowledge base: {str(e)}")
            return False
    
    def _format_context(self, results: List[Dict]) -> str:
        """Format retrieved context for the prompt."""
        formatted_context = ""
        
        for i, result in enumerate(results):
            title = result.get('title', 'No Title')
            content = result.get('content', 'No Content')
            
            formatted_context += f"\n\n--- CONTEXT {i+1} ---\n"
            formatted_context += f"Title: {title}\n\n"
            formatted_context += content
        
        return formatted_context
    
    def _build_prompt(self, query: str, contexts: List[Dict]) -> str:
        """Build a prompt for the LLM using retrieved contexts."""
        formatted_context = self._format_context(contexts)
        
        prompt = f"""You are an expert assistant for the game Baldur's Gate 3.

USER QUERY: {query}

RELEVANT CONTEXT:
{formatted_context}

INSTRUCTIONS:
1. Answer the user's query based ONLY on the provided context.
2. If the context doesn't contain enough information to fully answer the question, say so clearly.
3. Start with the most direct answer to the question, then provide additional details if relevant.
4. Cite the specific context (e.g., "According to Context 1...") when providing information.
5. If multiple contexts have conflicting information, acknowledge this and explain the differences.
6. Keep your response concise but informative.

YOUR RESPONSE:
"""
        return prompt
    
    def process_query(self, query: str, use_cache=True) -> str:
        """Process a user query through the complete RAG pipeline."""
        if not self.is_initialized:
            return "RAG system not initialized. Please call initialize() first."
        
        # Check cache if enabled
        if use_cache and query in self.query_cache:
            logger.info(f"Using cached response for: {query}")
            return self.query_cache[query]
        
        try:
            # 1. Search for relevant contexts
            contexts = self.search_engine.search(query, top_k=5)
            
            if not contexts:
                return "I couldn't find any relevant information to answer your question."
            
            # 2. Build prompt with retrieved contexts
            prompt = self._build_prompt(query, contexts)
            
            # 3. Generate response with LLM
            response = self.llm_interface.generate_response(prompt)
            
            # 4. Update cache
            if use_cache:
                if len(self.query_cache) >= self.cache_limit:
                    # Remove a random item to prevent unlimited growth
                    self.query_cache.pop(next(iter(self.query_cache)))
                self.query_cache[query] = response
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return f"Sorry, I encountered an error while processing your query: {str(e)}"


# ----- DEMO APPLICATION -----

def main():
    """Demo application for RAG system."""
    print("\n===== Modern RAG System Demo =====\n")
    
    # Initialize RAG system
    print("Initializing RAG system...")
    rag = RAGSystem(
        data_dir="data/wiki_processed",
        vector_db_dir="vector_db",
        embedding_model="BAAI/bge-small-en-v1.5"
    )
    
    if not rag.initialize():
        print("Failed to initialize RAG system. Please check the logs.")
        return
    
    print("\nRAG system initialized successfully!\n")
    
    # Interactive query loop
    print("Enter your questions about Baldur's Gate 3 (or type 'exit' to quit):")
    
    while True:
        try:
            query = input("\nQuestion > ")
            
            if query.lower() in ['exit', 'quit', 'q']:
                break
                
            if not query.strip():
                continue
                
            print("\nProcessing query...")
            start_time = time.time()
            
            response = rag.process_query(query)
            
            end_time = time.time()
            print(f"\nResponse (generated in {end_time - start_time:.2f}s):")
            print("-" * 50)
            print(response)
            print("-" * 50)
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {str(e)}")
    
    print("\nThank you for using the Modern RAG System Demo!")


if __name__ == "__main__":
    main()
