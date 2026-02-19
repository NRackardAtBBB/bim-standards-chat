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
import hashlib
import time

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
        # Force low threshold to 0.15. The embedding model might be returning low similarities for this domain.
        self.similarity_threshold = self.config.get_config('vector_search.similarity_threshold', 0.15)
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
        
        # Initialize query cache (TTL-based in-memory cache)
        self.query_cache = {}
        self.cache_ttl = 300  # 5 minutes TTL
    
    def _get_cache_key(self, query, n_results, search_type='hybrid'):
        """Generate cache key from query parameters."""
        cache_str = "{}|{}|{}".format(query.lower().strip(), n_results, search_type)
        return hashlib.md5(cache_str.encode('utf-8')).hexdigest()
    
    def _get_cached_results(self, cache_key):
        """Get cached results if not expired."""
        if cache_key in self.query_cache:
            cached_data = self.query_cache[cache_key]
            if time.time() - cached_data['timestamp'] < self.cache_ttl:
                return cached_data['results']
            else:
                # Expired, remove from cache
                del self.query_cache[cache_key]
        return None
    
    def _cache_results(self, cache_key, results):
        """Cache search results with timestamp."""
        self.query_cache[cache_key] = {
            'results': results,
            'timestamp': time.time()
        }
        
        # Simple cache cleanup: remove oldest entries if cache grows too large
        if len(self.query_cache) > 100:
            # Remove oldest 20 entries
            sorted_keys = sorted(self.query_cache.keys(), 
                               key=lambda k: self.query_cache[k]['timestamp'])
            for key in sorted_keys[:20]:
                del self.query_cache[key]
    
    def is_developer_mode_enabled(self):
        """Check if developer mode is enabled for current user."""
        developer_mode = self.config.get_config('vector_search.developer_mode', True)
        if not developer_mode:
            return True  # If not in developer mode, available to all

        # Check if current user is in whitelist
        whitelist = self.config.get_config('vector_search.developer_whitelist', [])

        # Safety: an empty whitelist would lock everyone out -- treat it as allow-all.
        # This prevents a config save bug from silently breaking vector search.
        if not whitelist:
            return True

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
    
    def get_embeddings_batch(self, texts):
        """
        Generate embeddings for multiple texts in a single API call.
        OpenAI supports up to 2048 texts and 300,000 tokens per request.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (list of floats)
        """
        if not texts:
            return []
        
        # OpenAI API limits: 2048 inputs AND 300,000 tokens per request
        # Use conservative limits to avoid errors
        max_texts_per_batch = 2048
        max_tokens_per_batch = 250000  # Leave safety margin
        
        all_embeddings = []
        current_batch = []
        current_token_count = 0
        batch_number = 1
        
        print("Generating embeddings for {} texts...".format(len(texts)))
        
        for i, text in enumerate(texts):
            # Count tokens in this text
            text_tokens = len(self.tokenizer.encode(text))
            
            # Check if adding this text would exceed limits
            would_exceed_tokens = (current_token_count + text_tokens) > max_tokens_per_batch
            would_exceed_count = len(current_batch) >= max_texts_per_batch
            
            # Process current batch if limits would be exceeded
            if current_batch and (would_exceed_tokens or would_exceed_count):
                print("  Batch {}: {} texts, {} tokens".format(
                    batch_number, len(current_batch), current_token_count
                ))
                response = self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=current_batch,
                    dimensions=self.embedding_dimensions
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                # Reset for next batch
                current_batch = []
                current_token_count = 0
                batch_number += 1
            
            # Add text to current batch
            current_batch.append(text)
            current_token_count += text_tokens
        
        # Process final batch
        if current_batch:
            print("  Batch {}: {} texts, {} tokens".format(
                batch_number, len(current_batch), current_token_count
            ))
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=current_batch,
                dimensions=self.embedding_dimensions
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
        
        print("Total embeddings generated: {}".format(len(all_embeddings)))
        return all_embeddings
    
    def index_documents(self, documents):
        """
        Index a list of documents into the vector database.
        
        Args:
            documents: List of document dicts with 'content', 'title', 'url', 'category', etc.
            
        Returns:
            Dict with counts of documents and chunks indexed
        """
        total_chunks = 0
        
        # Collect all chunks first for batch embedding
        all_chunks = []
        all_chunk_ids = []
        all_chunk_metadata = []
        
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
            
            # Collect chunks for batch processing
            for chunk in chunks:
                chunk_id = "{}_chunk_{}".format(base_metadata['doc_id'], chunk['metadata']['chunk_index'])
                all_chunks.append(chunk['content'])
                all_chunk_ids.append(chunk_id)
                all_chunk_metadata.append(chunk['metadata'])
                total_chunks += 1
        
        # Generate embeddings in batch (MAJOR PERFORMANCE IMPROVEMENT)
        if all_chunks:
            embeddings = self.get_embeddings_batch(all_chunks)
            
            # Add all chunks to ChromaDB
            self.collection.add(
                ids=all_chunk_ids,
                embeddings=embeddings,
                documents=all_chunks,
                metadatas=all_chunk_metadata
            )
        
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
        Perform keyword-based search using ChromaDB's where_document filtering.
        More efficient than loading all documents into memory.
        
        Args:
            query: Search query text
            n_results: Number of results to return
            
        Returns:
            List of result dicts matching semantic_search format
        """
        if n_results is None:
            n_results = self.max_results
        
        # Extract keywords (simple split on whitespace and remove short words)
        keywords = [k for k in query.lower().split() if len(k) > 2]
        
        if not keywords:
            return []
        
        # Use ChromaDB's where_document filter for efficient text search
        # Query for documents containing any of the keywords
        scored_results = []
        
        for keyword in keywords:
            try:
                # Use $contains operator for substring matching
                results = self.collection.get(
                    where_document={"$contains": keyword},
                    include=['metadatas', 'documents']
                )
                
                # Score results based on keyword relevance
                for i, doc_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i]
                    content = results['documents'][i]
                    title = metadata.get('title', '').lower()
                    content_lower = content.lower()
                    
                    # Calculate score for this keyword
                    score = 0
                    # Title matches worth more (10 points per occurrence)
                    score += title.count(keyword) * 10
                    # Content matches (1 point per occurrence)
                    score += content_lower.count(keyword)
                    
                    # Check if we already have this document from another keyword
                    existing = next((r for r in scored_results if r['chunk_id'] == doc_id), None)
                    if existing:
                        # Add to existing score
                        existing['score'] += score
                    else:
                        # Add new result
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
            except Exception as e:
                # If where_document fails, continue with other keywords
                continue
        
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
    
    def deduplicate_by_url(self, results, max_chunks_per_url=2):
        """
        Deduplicate results by URL, keeping top N scoring chunks per page.
        This preserves context from multiple relevant sections of the same document.
        
        Args:
            results: List of results potentially with multiple chunks from same page
            max_chunks_per_url: Maximum number of chunks to keep per unique URL (default: 2)
            
        Returns:
            Deduplicated results with up to max_chunks_per_url entries per unique URL
        """
        url_map = {}
        
        for result in results:
            url = result['url']
            if url not in url_map:
                url_map[url] = []
            url_map[url].append(result)
        
        # Keep top N chunks per URL
        deduplicated = []
        for url, chunks in url_map.items():
            # Sort chunks by score and take top N
            chunks.sort(key=lambda x: x['score'], reverse=True)
            deduplicated.extend(chunks[:max_chunks_per_url])
        
        # Return sorted by score
        deduplicated.sort(key=lambda x: x['score'], reverse=True)
        return deduplicated
    def get_all_titles(self):
        """Get list of all unique document titles in the database."""
        try:
            result = self.collection.get(include=['metadatas'])
            titles = set()
            for meta in result['metadatas']:
                if meta and 'title' in meta:
                    titles.add(meta['title'])
            return sorted(list(titles))
        except:
            return []

    def hybrid_search(self, query, n_results=None, deduplicate=True):
        """
        Perform hybrid search combining semantic and keyword approaches.
        Uses TTL-based caching to avoid redundant API calls for identical queries.
        
        Args:
            query: Search query text
            n_results: Number of results to return
            deduplicate: Whether to deduplicate by URL
            
        Returns:
            List of merged and ranked results
        """
        if n_results is None:
            n_results = self.max_results
        
        # Check for meta-queries about available documents
        query_lower = query.lower()
        meta_triggers = ["what do you have access to", "what information", "what documents", "what standards", "list available", "available standards", "documents do you have", "what can you see"]
        
        synthetic_results = []
        if any(trigger in query_lower for trigger in meta_triggers):
            all_titles = self.get_all_titles()
            if all_titles:
                title_list = "\n".join(["- " + t for t in all_titles])
                synthetic_results.append({
                    'id': 'system_index',
                    'chunk_id': 'system_index_0',
                    'title': 'System Index: All Available Standards',
                    'url': 'system:index',
                    'content': "The following is a complete list of all standard documents currently indexed and available for retrieval:\n\n" + title_list + "\n\nUse this list to identify which specific standards the user might be interested in.",
                    'category': 'System',
                    'score': 2.0, # Force to top
                    'normalized_score': 1.0,
                    'hybrid_score': 2.0,
                    'chunk_index': 0,
                    'total_chunks': 1,
                    'last_updated': datetime.now().isoformat()
                })

        # Check cache first
        cache_key = self._get_cache_key(query, n_results, 'hybrid')
        cached_results = self._get_cached_results(cache_key)
        if cached_results is not None:
            return cached_results
        
        # Perform both searches (get more results for merging)
        semantic_results = self.semantic_search(query, n_results * 2)
        keyword_results = self.keyword_search(query, n_results * 2)
        
        # NOTE: We do NOT normalize semantic scores anymore, as they are cosine similarities
        # that roughly map to absolute relevance (0-1). Normalizing them by batch min/max
        # caused good results to be scored 0.0 if they were the "least good" in a good batch.
        # keyword_results still need normalization as they are unbounded counts.
        keyword_results = self.normalize_scores(keyword_results)
        
        # Merge results by chunk_id
        merged_map = {}
        
        # Add semantic results (using raw score as normalized_score)
        for result in semantic_results:
            chunk_id = result['chunk_id']
            # Treat raw cosine similarity as the normalized score
            result['normalized_score'] = result['score'] 
            
            merged_map[chunk_id] = result.copy()
            # If search term is explicitly in title, boost semantic score significantly
            title_boost = 0.0
            title_lower = result.get('title', '').lower()
            if any(term in title_lower for term in query.lower().split() if len(term) > 3):
                 title_boost = 0.2
            
            # Massive boost if exact acronym match
            if 'pdso' in query.lower() and 'pdso' in title_lower:
                title_boost = 0.4

            merged_map[chunk_id]['hybrid_score'] = (result['score'] + title_boost) * self.semantic_weight
            merged_map[chunk_id]['semantic_score'] = result['score'] + title_boost
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
        # Prepend synthetic results (forcing them to be included)
        final_results = synthetic_results + merged_results[:n_results]
        
        # Cache the results
        self._cache_results(cache_key, final_results)
        
        return final_results
    
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
