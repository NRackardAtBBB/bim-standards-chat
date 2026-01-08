#! python3
"""
Vector database client for semantic search using ChromaDB and OpenAI embeddings.
Provides chunking, indexing, and hybrid search capabilities for SharePoint content.

NOTE: This module uses cpython engine (not IronPython) to access third-party packages.
Ensure you have Python 3.12.3 installed and packages installed via pip.
"""
import sys
import os

# Add your Python site-packages to path
# Find this path with: python -c "import site; print(site.getsitepackages()[0])"
# Example paths (uncomment and update for your system):
# sys.path.append(r'C:\Users\nrackard\AppData\Local\Programs\Python\Python312\Lib\site-packages')
# sys.path.append(r'C:\Users\nrackard\AppData\Local\Programs\Python\Python312\Lib')

# Auto-detect site-packages if Python is in PATH
try:
    import site
    for path in site.getsitepackages():
        if path not in sys.path:
            sys.path.append(path)
except:
    pass

import json
from datetime import datetime

try:
    import chromadb
    from chromadb.config import Settings
    from openai import OpenAI
    import tiktoken
except ImportError as e:
    raise ImportError(
        "Required packages not found. Please install:\n"
        "  pip install chromadb openai tiktoken\n"
        "See VECTOR_SEARCH_QUICKSTART.md for installation instructions.\n"
        "Original error: {}".format(e)
    )


class VectorDBClient:
    """Manages vector database operations for semantic search."""
    
    def __init__(self, config_manager):
        """
        Initialize the vector database client.
        
        Args:
            config_manager: ConfigManager instance for accessing configuration
        """
        self.config = config_manager
        self.openai_api_key = config_manager.get_api_key('openai')
        
        # OpenAI client for embeddings
        self.openai_client = OpenAI(api_key=self.openai_api_key)
        
        # Vector search configuration
        self.embedding_model = self.config.get_config('vector_search.embedding_model', 'text-embedding-3-small')
        self.embedding_dimensions = self.config.get_config('vector_search.embedding_dimensions', 1536)
        self.chunk_size = self.config.get_config('vector_search.chunk_size', 500)
        self.chunk_overlap = self.config.get_config('vector_search.chunk_overlap', 100)
        self.max_results = self.config.get_config('vector_search.max_results', 10)
        self.similarity_threshold = self.config.get_config('vector_search.similarity_threshold', 0.5)
        self.semantic_weight = self.config.get_config('vector_search.hybrid_search_weight_semantic', 0.7)
        self.keyword_weight = self.config.get_config('vector_search.hybrid_search_weight_keyword', 0.3)
        
        # Initialize ChromaDB
        db_path = self.config.get_config('vector_search.db_path', 'vector_db')
        # Make path absolute relative to config directory
        config_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.db_path = os.path.join(config_dir, 'config', db_path)
        
        self.client = chromadb.PersistentClient(
            path=self.db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="sharepoint_pages",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Initialize tokenizer for chunking
        self.tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")
    
    def is_developer_mode_enabled(self):
        """Check if developer mode is enabled for current user."""
        developer_mode = self.config.get_config('vector_search.developer_mode', True)
        if not developer_mode:
            return True  # If not in developer mode, available to all
        
        # Check if current user is in whitelist
        whitelist = self.config.get_config('vector_search.developer_whitelist', [])
        current_user = os.environ.get('USERNAME', '').lower()
        return current_user in [u.lower() for u in whitelist]
    
    def chunk_text(self, text, metadata):
        """
        Split text into overlapping chunks based on token count.
        
        Args:
            text: Text to chunk
            metadata: Base metadata to attach to each chunk
            
        Returns:
            List of chunk dictionaries with content and metadata
        """
        # Tokenize the text
        tokens = self.tokenizer.encode(text)
        chunks = []
        
        # Split into overlapping chunks
        start = 0
        chunk_index = 0
        
        while start < len(tokens):
            # Get chunk tokens
            end = start + self.chunk_size
            chunk_tokens = tokens[start:end]
            
            # Decode back to text
            chunk_text = self.tokenizer.decode(chunk_tokens)
            
            # Create chunk with metadata (merge manually for IronPython compatibility)
            chunk_metadata = {}
            chunk_metadata.update(metadata)
            chunk_metadata['chunk_index'] = chunk_index
            chunk_metadata['chunk_start_token'] = start
            chunk_metadata['chunk_end_token'] = min(end, len(tokens))
            
            chunk = {
                'content': chunk_text,
                'metadata': chunk_metadata
            }
            chunks.append(chunk)
            
            # Move to next chunk with overlap
            start += self.chunk_size - self.chunk_overlap
            chunk_index += 1
        
        # Update total_chunks in all chunk metadata
        for chunk in chunks:
            chunk['metadata']['total_chunks'] = len(chunks)
        
        return chunks
    
    def get_embedding(self, text):
        """
        Generate embedding vector for text using OpenAI API.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        response = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=text,
            dimensions=self.embedding_dimensions
        )
        return response.data[0].embedding
    
    def index_documents(self, documents):
        """
        Index a list of documents into the vector database.
        
        Args:
            documents: List of document dicts with 'content', 'title', 'url', 'category', etc.
            
        Returns:
            Dict with counts of documents and chunks indexed
        """
        total_chunks = 0
        
        for doc in documents:
            # Extract document content and metadata
            content = doc.get('content', '')
            if not content:
                continue
            
            base_metadata = {
                'title': doc.get('title', 'Untitled'),
                'url': doc.get('url', ''),
                'category': doc.get('category', 'General'),
                'doc_id': doc.get('id', ''),
                'last_updated': doc.get('last_updated', '')
            }
            
            # Chunk the document
            chunks = self.chunk_text(content, base_metadata)
            
            # Generate embeddings and add to collection
            for chunk in chunks:
                chunk_id = "{}_chunk_{}".format(base_metadata['doc_id'], chunk['metadata']['chunk_index'])
                embedding = self.get_embedding(chunk['content'])
                
                # Add to ChromaDB
                self.collection.add(
                    ids=[chunk_id],
                    embeddings=[embedding],
                    documents=[chunk['content']],
                    metadatas=[chunk['metadata']]
                )
                total_chunks += 1
        
        return {
            'documents': len(documents),
            'chunks': total_chunks
        }
    
    def clear_collection(self):
        """Clear all documents from the collection."""
        # Delete and recreate collection
        self.client.delete_collection("sharepoint_pages")
        self.collection = self.client.get_or_create_collection(
            name="sharepoint_pages",
            metadata={"hnsw:space": "cosine"}
        )
    
    def semantic_search(self, query, n_results=None):
        """
        Perform semantic search using vector similarity.
        
        Args:
            query: Search query text
            n_results: Number of results to return (defaults to config max_results)
            
        Returns:
            List of result dicts with 'id', 'title', 'url', 'content', 'category', 'score'
        """
        if n_results is None:
            n_results = self.max_results
        
        # Generate query embedding
        query_embedding = self.get_embedding(query)
        
        # Search ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        # Format results
        formatted_results = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                # Calculate similarity score (cosine distance -> similarity)
                distance = results['distances'][0][i]
                similarity = 1 - distance  # Convert distance to similarity
                
                # Skip if below threshold
                if similarity < self.similarity_threshold:
                    continue
                
                metadata = results['metadatas'][0][i]
                formatted_results.append({
                    'id': metadata.get('doc_id', results['ids'][0][i]),
                    'chunk_id': results['ids'][0][i],
                    'title': metadata.get('title', 'Untitled'),
                    'url': metadata.get('url', ''),
                    'content': results['documents'][0][i],
                    'category': metadata.get('category', 'General'),
                    'score': similarity,
                    'chunk_index': metadata.get('chunk_index', 0),
                    'total_chunks': metadata.get('total_chunks', 1),
                    'last_updated': metadata.get('last_updated', '')
                })
        
        return formatted_results
    
    def keyword_search(self, query, n_results=None):
        """
        Perform keyword-based search using metadata filtering.
        
        Args:
            query: Search query text
            n_results: Number of results to return
            
        Returns:
            List of result dicts matching semantic_search format
        """
        if n_results is None:
            n_results = self.max_results
        
        # Extract keywords (simple split on whitespace)
        keywords = query.lower().split()
        
        # Get all documents
        all_docs = self.collection.get(include=['metadatas', 'documents'])
        
        # Score documents based on keyword matches
        scored_results = []
        for i, doc_id in enumerate(all_docs['ids']):
            metadata = all_docs['metadatas'][i]
            content = all_docs['documents'][i]
            
            # Calculate keyword match score
            title = metadata.get('title', '').lower()
            content_lower = content.lower()
            
            score = 0
            for keyword in keywords:
                # Title matches worth more
                if keyword in title:
                    score += 10
                # Content matches
                score += content_lower.count(keyword)
            
            if score > 0:
                scored_results.append({
                    'id': metadata.get('doc_id', doc_id),
                    'chunk_id': doc_id,
                    'title': metadata.get('title', 'Untitled'),
                    'url': metadata.get('url', ''),
                    'content': content,
                    'category': metadata.get('category', 'General'),
                    'score': score,
                    'chunk_index': metadata.get('chunk_index', 0),
                    'total_chunks': metadata.get('total_chunks', 1),
                    'last_updated': metadata.get('last_updated', '')
                })
        
        # Sort by score and return top results
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        return scored_results[:n_results]
    
    def normalize_scores(self, results):
        """
        Normalize scores to 0-1 range using min-max scaling.
        
        Args:
            results: List of results with 'score' field
            
        Returns:
            Results with normalized scores
        """
        if not results:
            return results
        
        scores = [r['score'] for r in results]
        min_score = min(scores)
        max_score = max(scores)
        
        # Avoid division by zero
        if max_score == min_score:
            for result in results:
                result['normalized_score'] = 1.0
            return results
        
        # Normalize to 0-1
        for result in results:
            result['normalized_score'] = (result['score'] - min_score) / (max_score - min_score)
        
        return results
    
    def deduplicate_by_url(self, results):
        """
        Deduplicate results by URL, keeping highest scoring chunk per page.
        
        Args:
            results: List of results potentially with multiple chunks from same page
            
        Returns:
            Deduplicated results with one entry per unique URL
        """
        url_map = {}
        
        for result in results:
            url = result['url']
            if url not in url_map or result['score'] > url_map[url]['score']:
                url_map[url] = result
        
        # Return sorted by score
        deduplicated = list(url_map.values())
        deduplicated.sort(key=lambda x: x['score'], reverse=True)
        return deduplicated
    
    def hybrid_search(self, query, n_results=None, deduplicate=True):
        """
        Perform hybrid search combining semantic and keyword approaches.
        
        Args:
            query: Search query text
            n_results: Number of results to return
            deduplicate: Whether to deduplicate by URL
            
        Returns:
            List of merged and ranked results
        """
        if n_results is None:
            n_results = self.max_results
        
        # Perform both searches (get more results for merging)
        semantic_results = self.semantic_search(query, n_results * 2)
        keyword_results = self.keyword_search(query, n_results * 2)
        
        # Normalize scores for each result set
        semantic_results = self.normalize_scores(semantic_results)
        keyword_results = self.normalize_scores(keyword_results)
        
        # Merge results by chunk_id
        merged_map = {}
        
        # Add semantic results
        for result in semantic_results:
            chunk_id = result['chunk_id']
            merged_map[chunk_id] = result.copy()
            merged_map[chunk_id]['hybrid_score'] = result['normalized_score'] * self.semantic_weight
            merged_map[chunk_id]['semantic_score'] = result['normalized_score']
            merged_map[chunk_id]['keyword_score'] = 0
        
        # Add/merge keyword results
        for result in keyword_results:
            chunk_id = result['chunk_id']
            if chunk_id in merged_map:
                # Update hybrid score
                merged_map[chunk_id]['keyword_score'] = result['normalized_score']
                merged_map[chunk_id]['hybrid_score'] += result['normalized_score'] * self.keyword_weight
            else:
                # Add new result
                merged_map[chunk_id] = result.copy()
                merged_map[chunk_id]['hybrid_score'] = result['normalized_score'] * self.keyword_weight
                merged_map[chunk_id]['semantic_score'] = 0
                merged_map[chunk_id]['keyword_score'] = result['normalized_score']
        
        # Convert to list and sort by hybrid score
        merged_results = list(merged_map.values())
        merged_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        
        # Update score field to hybrid_score for consistency
        for result in merged_results:
            result['score'] = result['hybrid_score']
        
        # Deduplicate if requested
        if deduplicate:
            merged_results = self.deduplicate_by_url(merged_results)
        
        # Return top n results
        return merged_results[:n_results]
    
    def get_stats(self):
        """
        Get statistics about the indexed collection.
        
        Returns:
            Dict with document count, chunk count, last sync time
        """
        # Get collection count
        count = self.collection.count()
        
        # Get unique document count
        all_docs = self.collection.get(include=['metadatas'])
        unique_doc_ids = set()
        for metadata in all_docs['metadatas']:
            doc_id = metadata.get('doc_id', '')
            if doc_id:
                unique_doc_ids.add(doc_id)
        
        return {
            'total_chunks': count,
            'unique_documents': len(unique_doc_ids),
            'last_sync': self.config.get_config('vector_search.last_sync_timestamp', None)
        }
