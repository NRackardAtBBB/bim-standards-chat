#! python3
# -*- coding: utf-8 -*-
"""
Vector database client for semantic search using numpy and OpenAI embeddings.
Provides chunking, indexing, and hybrid search capabilities for SharePoint content.

Uses numpy (ships with pyRevit's bundled CPython) for cosine similarity and
urllib.request (Python stdlib) for OpenAI API calls — no pip install required.
"""
import sys
import os
import json
import hashlib
import time
import io
from datetime import datetime

import numpy as np
import urllib.request
import urllib.error


class VectorDBClient:
    """Manages vector database operations for semantic search."""

    def __init__(self, config_manager):
        """
        Initialize the vector database client.

        Args:
            config_manager: ConfigManager instance for accessing configuration
        """
        self.config = config_manager
        self.api_key = config_manager.get_api_key('openai')

        # Vector search configuration
        self.embedding_model = self.config.get_config('vector_search.embedding_model', 'text-embedding-3-small')
        self.embedding_dimensions = self.config.get_config('vector_search.embedding_dimensions', 1536)
        self.chunk_size = self.config.get_config('vector_search.chunk_size', 500)
        self.chunk_overlap = self.config.get_config('vector_search.chunk_overlap', 100)
        self.max_results = self.config.get_config('vector_search.max_results', 10)
        self.similarity_threshold = self.config.get_config('vector_search.similarity_threshold', 0.15)
        self.semantic_weight = self.config.get_config('vector_search.hybrid_search_weight_semantic', 0.7)
        self.keyword_weight = self.config.get_config('vector_search.hybrid_search_weight_keyword', 0.3)

        # Paths
        db_path_rel = self.config.get_config('vector_search.db_path', 'vector_db')
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config')
        self.db_dir = os.path.join(config_dir, db_path_rel)
        self.vectors_path = os.path.join(self.db_dir, 'vectors.npz')
        self.metadata_path = os.path.join(self.db_dir, 'metadata.json')

        self._embedding_cache_path = os.path.join(
            os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
            'BBB', 'Kodama', 'embedding_cache.json'
        )
        self._embedding_cache = None
        self._embedding_cache_dirty = False

        # Lazy-loaded index: (np.ndarray shape (N,D), list of metadata dicts)
        self._index = None

        # In-memory query cache (TTL-based)
        self.query_cache = {}
        self.cache_ttl = 300

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _tlog(self, message):
        """Write a timing/debug message to the shared debug log."""
        try:
            log_dir = os.path.join(os.environ.get('APPDATA', ''), 'BBB', 'StandardsAssistant')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            log_path = os.path.join(log_dir, 'debug_log.txt')
            with io.open(log_path, 'a', encoding='utf-8') as f:
                f.write(u"{} [vector_db] {}\n".format(datetime.now().isoformat(), message))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Embedding cache helpers
    # ------------------------------------------------------------------

    def _load_embedding_cache(self):
        """Load the persisted embedding cache from disk (lazy, called once)."""
        if self._embedding_cache is not None:
            return
        try:
            if os.path.exists(self._embedding_cache_path):
                with open(self._embedding_cache_path, 'r', encoding='utf-8') as f:
                    self._embedding_cache = json.load(f)
                self._tlog("embedding_cache: loaded {} entries from disk".format(
                    len(self._embedding_cache)))
            else:
                self._embedding_cache = {}
        except Exception as e:
            self._tlog("embedding_cache: load failed ({}), starting empty".format(e))
            self._embedding_cache = {}

    def _flush_embedding_cache(self):
        """Persist any new cache entries to disk."""
        if not self._embedding_cache_dirty:
            return
        try:
            cache_dir = os.path.dirname(self._embedding_cache_path)
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            with open(self._embedding_cache_path, 'w', encoding='utf-8') as f:
                json.dump(self._embedding_cache, f)
            self._embedding_cache_dirty = False
        except Exception as e:
            self._tlog("embedding_cache: flush failed: {}".format(e))

    def _embedding_cache_key(self, text):
        """Stable cache key: SHA256 of model|dimensions|text."""
        raw = u"{}|{}|{}".format(self.embedding_model, self.embedding_dimensions, text)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    # ------------------------------------------------------------------
    # OpenAI embeddings via urllib (no openai package needed)
    # ------------------------------------------------------------------

    def _call_openai_embeddings(self, texts, attempt=0):
        """
        POST to OpenAI /v1/embeddings and return list of embedding vectors.
        Retries up to 3 times with exponential backoff.
        """
        payload = json.dumps({
            'model': self.embedding_model,
            'input': texts,
            'dimensions': self.embedding_dimensions
        }).encode('utf-8')

        req = urllib.request.Request(
            'https://api.openai.com/v1/embeddings',
            data=payload,
            headers={
                'Authorization': 'Bearer ' + self.api_key,
                'Content-Type': 'application/json'
            }
        )
        try:
            resp = urllib.request.urlopen(req, timeout=60)
            data = json.loads(resp.read().decode('utf-8'))
            # API returns items sorted by index
            return [item['embedding'] for item in sorted(data['data'], key=lambda x: x['index'])]
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            if e.code == 429 and attempt < 3:
                wait = 2 ** attempt
                self._tlog("OpenAI rate-limit, retrying in {}s".format(wait))
                time.sleep(wait)
                return self._call_openai_embeddings(texts, attempt + 1)
            raise RuntimeError("OpenAI API error {}: {}".format(e.code, body[:200]))
        except Exception:
            if attempt < 3:
                time.sleep(2 ** attempt)
                return self._call_openai_embeddings(texts, attempt + 1)
            raise

    def get_embedding(self, text):
        """
        Generate embedding vector for text. Results are cached to disk.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        self._load_embedding_cache()
        key = self._embedding_cache_key(text)

        if key in self._embedding_cache:
            self._tlog("embedding_cache: HIT")
            return self._embedding_cache[key]

        self._tlog("embedding_cache: MISS – calling OpenAI")
        embeddings = self._call_openai_embeddings([text])
        embedding = embeddings[0]

        self._embedding_cache[key] = embedding
        self._embedding_cache_dirty = True
        self._flush_embedding_cache()
        return embedding

    def get_embeddings_batch(self, texts):
        """
        Generate embeddings for multiple texts, using the disk cache where possible.
        Uncached texts are sent to OpenAI in a single batched request.

        Args:
            texts: List of text strings

        Returns:
            List of embedding vectors (list of floats), same order as input
        """
        if not texts:
            return []

        self._load_embedding_cache()

        # Separate cached from uncached
        keys = [self._embedding_cache_key(t) for t in texts]
        uncached_indices = [i for i, k in enumerate(keys) if k not in self._embedding_cache]
        uncached_texts = [texts[i] for i in uncached_indices]

        if uncached_texts:
            print("Generating embeddings for {} texts ({} cached, {} new)...".format(
                len(texts), len(texts) - len(uncached_texts), len(uncached_texts)))

            # Batch into chunks of 2048 (OpenAI limit)
            batch_size = 2048
            new_embeddings = []
            for start in range(0, len(uncached_texts), batch_size):
                batch = uncached_texts[start:start + batch_size]
                print("  Sending batch of {} texts to OpenAI...".format(len(batch)))
                new_embeddings.extend(self._call_openai_embeddings(batch))

            # Store new embeddings in cache
            for i, embedding in zip(uncached_indices, new_embeddings):
                self._embedding_cache[keys[i]] = embedding
            self._embedding_cache_dirty = True
            self._flush_embedding_cache()

        return [self._embedding_cache[k] for k in keys]

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def chunk_text(self, text, metadata):
        """
        Split text into overlapping chunks based on approximate word count.
        (Replaces tiktoken-based tokenization; 0.75 words ≈ 1 token.)

        Args:
            text: Text to chunk
            metadata: Base metadata dict to attach to each chunk

        Returns:
            List of chunk dicts with 'content' and 'metadata'
        """
        words_per_chunk = max(1, int(self.chunk_size * 0.75))
        words_overlap = max(0, int(self.chunk_overlap * 0.75))
        step = max(1, words_per_chunk - words_overlap)

        words = text.split()
        chunks = []
        chunk_index = 0
        start = 0

        while start < len(words):
            end = start + words_per_chunk
            chunk_words = words[start:end]
            chunk_text_str = u' '.join(chunk_words)

            chunk_metadata = {}
            chunk_metadata.update(metadata)
            chunk_metadata['chunk_index'] = chunk_index
            chunk_metadata['chunk_start_word'] = start
            chunk_metadata['chunk_end_word'] = min(end, len(words))

            chunks.append({
                'content': chunk_text_str,
                'metadata': chunk_metadata
            })
            start += step
            chunk_index += 1

        for chunk in chunks:
            chunk['metadata']['total_chunks'] = len(chunks)

        return chunks

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _load_index(self):
        """Load vectors.npz + metadata.json into memory (cached after first call)."""
        if self._index is not None:
            return self._index

        if not os.path.exists(self.vectors_path) or not os.path.exists(self.metadata_path):
            return None

        try:
            t0 = time.time()
            npz = np.load(self.vectors_path)
            embeddings = npz['embeddings']  # shape (N, D), already normalised
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                metadata_list = json.load(f)
            self._tlog("TIMING _load_index={:.2f}s chunks={}".format(time.time() - t0, len(metadata_list)))
            self._index = (embeddings, metadata_list)
            return self._index
        except Exception as e:
            self._tlog("_load_index error: {}".format(e))
            return None

    def index_documents(self, documents):
        """
        Index a list of documents into the numpy vector store.

        Args:
            documents: List of document dicts with 'content', 'title', 'url', 'category', etc.

        Returns:
            Dict with counts of documents and chunks indexed
        """
        all_texts = []
        all_metadata = []

        for doc in documents:
            content = doc.get('content', '')
            if not content:
                continue

            base_metadata = {
                'title': doc.get('title', 'Untitled'),
                'url': doc.get('url', ''),
                'category': doc.get('category', 'General'),
                'doc_id': doc.get('id', ''),
                'last_updated': doc.get('last_updated', ''),
            }

            chunks = self.chunk_text(content, base_metadata)
            for chunk in chunks:
                all_texts.append(chunk['content'])
                # Store text inside metadata for retrieval
                meta = dict(chunk['metadata'])
                meta['text'] = chunk['content']
                all_metadata.append(meta)

        if not all_texts:
            return {'documents': len(documents), 'chunks': 0}

        embeddings_list = self.get_embeddings_batch(all_texts)
        embeddings = np.array(embeddings_list, dtype=np.float32)

        # Pre-normalise rows so dot product == cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)  # avoid div-by-zero
        embeddings /= norms

        if not os.path.exists(self.db_dir):
            os.makedirs(self.db_dir)

        np.savez_compressed(self.vectors_path, embeddings=embeddings)
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, ensure_ascii=False)

        # Reset in-memory index so next search loads fresh data
        self._index = None

        # Update config stats
        try:
            self.config.set_config('vector_search.last_sync_timestamp', datetime.now().isoformat())
            self.config.set_config('vector_search.indexed_document_count', len(documents))
            self.config.set_config('vector_search.indexed_chunk_count', len(all_texts))
            self.config.save()
        except Exception:
            pass

        return {'documents': len(documents), 'chunks': len(all_texts)}

    def clear_collection(self):
        """Delete the stored index files."""
        for path in (self.vectors_path, self.metadata_path):
            if os.path.exists(path):
                os.remove(path)
        self._index = None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def semantic_search(self, query, n_results=None):
        """
        Perform semantic search using cosine similarity via numpy.

        Args:
            query: Search query text
            n_results: Number of results to return

        Returns:
            List of result dicts with 'id', 'title', 'url', 'content', 'category', 'score'
        """
        if n_results is None:
            n_results = self.max_results

        index = self._load_index()
        if index is None:
            self._tlog("semantic_search: no index found")
            return []

        embeddings, metadata_list = index

        t0_embed = time.time()
        query_vec = np.array(self.get_embedding(query), dtype=np.float32)
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            query_vec /= norm
        self._tlog("TIMING semantic_search.get_embedding={:.2f}s".format(time.time() - t0_embed))

        t0_sim = time.time()
        scores = np.dot(embeddings, query_vec)  # (N,) cosine similarities
        # Over-fetch for deduplication downstream
        k = min(n_results * 3, len(scores))
        top_indices = np.argsort(scores)[::-1][:k]
        self._tlog("TIMING semantic_search.dot_product={:.2f}s".format(time.time() - t0_sim))

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score < self.similarity_threshold:
                continue
            meta = metadata_list[idx]
            results.append({
                'id': meta.get('doc_id', str(idx)),
                'chunk_id': "{}_chunk_{}".format(meta.get('doc_id', str(idx)), meta.get('chunk_index', 0)),
                'title': meta.get('title', 'Untitled'),
                'url': meta.get('url', ''),
                'content': meta.get('text', ''),
                'category': meta.get('category', 'General'),
                'score': score,
                'chunk_index': meta.get('chunk_index', 0),
                'total_chunks': meta.get('total_chunks', 1),
                'last_updated': meta.get('last_updated', ''),
            })

        return results

    def keyword_search(self, query, n_results=None):
        """
        Perform keyword-based search over the metadata store.

        Args:
            query: Search query text
            n_results: Number of results to return

        Returns:
            List of result dicts matching semantic_search format
        """
        if n_results is None:
            n_results = self.max_results

        index = self._load_index()
        if index is None:
            return []

        _, metadata_list = index

        _STOP_WORDS = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can',
            'her', 'was', 'one', 'our', 'out', 'had', 'his', 'has', 'have',
            'him', 'its', 'may', 'did', 'get', 'use', 'how', 'any', 'who',
            'own', 'new', 'way', 'too', 'few', 'now', 'let', 'put', 'set',
            'what', 'that', 'this', 'with', 'they', 'from', 'will', 'been',
            'when', 'more', 'also', 'into', 'some', 'than', 'then', 'them',
            'there', 'their', 'about', 'which', 'would', 'these', 'other',
            'where', 'right', 'just', 'does', 'each', 'most', 'such', 'even',
            'were', 'your', 'very', 'make', 'over', 'same', 'back', 'after',
            'could', 'while', 'both', 'need', 'should', 'those', 'want',
        }
        keywords = [k for k in query.lower().split() if len(k) > 2 and k not in _STOP_WORDS]

        if not keywords:
            return []

        t0 = time.time()
        scored = {}  # chunk_id -> result dict

        for idx, meta in enumerate(metadata_list):
            content_lower = meta.get('text', '').lower()
            title_lower = meta.get('title', '').lower()

            score = 0
            for kw in keywords:
                score += title_lower.count(kw) * 10
                score += content_lower.count(kw)

            if score == 0:
                continue

            chunk_id = "{}_chunk_{}".format(meta.get('doc_id', str(idx)), meta.get('chunk_index', 0))
            if chunk_id in scored:
                scored[chunk_id]['score'] += score
            else:
                scored[chunk_id] = {
                    'id': meta.get('doc_id', str(idx)),
                    'chunk_id': chunk_id,
                    'title': meta.get('title', 'Untitled'),
                    'url': meta.get('url', ''),
                    'content': meta.get('text', ''),
                    'category': meta.get('category', 'General'),
                    'score': score,
                    'chunk_index': meta.get('chunk_index', 0),
                    'total_chunks': meta.get('total_chunks', 1),
                    'last_updated': meta.get('last_updated', ''),
                }

        self._tlog("TIMING keyword_search={:.2f}s results={}".format(time.time() - t0, len(scored)))
        results = sorted(scored.values(), key=lambda x: x['score'], reverse=True)
        return results[:n_results]

    # ------------------------------------------------------------------
    # Unchanged helpers (no ChromaDB calls)
    # ------------------------------------------------------------------

    def _get_cache_key(self, query, n_results, search_type='hybrid'):
        cache_str = "{}|{}|{}".format(query.lower().strip(), n_results, search_type)
        return hashlib.md5(cache_str.encode('utf-8')).hexdigest()

    def _get_cached_results(self, cache_key):
        if cache_key in self.query_cache:
            cached_data = self.query_cache[cache_key]
            if time.time() - cached_data['timestamp'] < self.cache_ttl:
                return cached_data['results']
            del self.query_cache[cache_key]
        return None

    def _cache_results(self, cache_key, results):
        self.query_cache[cache_key] = {'results': results, 'timestamp': time.time()}
        if len(self.query_cache) > 100:
            sorted_keys = sorted(self.query_cache, key=lambda k: self.query_cache[k]['timestamp'])
            for key in sorted_keys[:20]:
                del self.query_cache[key]

    def normalize_scores(self, results):
        """Normalize scores to 0-1 range using min-max scaling."""
        if not results:
            return results
        scores = [r['score'] for r in results]
        min_score = min(scores)
        max_score = max(scores)
        if max_score == min_score:
            for r in results:
                r['normalized_score'] = 1.0
            return results
        for r in results:
            r['normalized_score'] = (r['score'] - min_score) / (max_score - min_score)
        return results

    def deduplicate_by_url(self, results, max_chunks_per_url=2):
        """Deduplicate results by URL, keeping top N scoring chunks per page."""
        url_map = {}
        for result in results:
            url = result['url']
            if url not in url_map:
                url_map[url] = []
            url_map[url].append(result)
        deduplicated = []
        for chunks in url_map.values():
            chunks.sort(key=lambda x: x['score'], reverse=True)
            deduplicated.extend(chunks[:max_chunks_per_url])
        deduplicated.sort(key=lambda x: x['score'], reverse=True)
        return deduplicated

    def get_all_titles(self):
        """Get list of all unique document titles in the index."""
        index = self._load_index()
        if index is None:
            return []
        _, metadata_list = index
        titles = set()
        for meta in metadata_list:
            if meta.get('title'):
                titles.add(meta['title'])
        return sorted(titles)

    def is_developer_mode_enabled(self):
        """Check if developer mode is enabled for current user."""
        developer_mode = self.config.get_config('vector_search.developer_mode', True)
        if not developer_mode:
            return True

        whitelist = self.config.api_keys.get('admin_whitelist', None)
        if whitelist is None:
            whitelist = self.config.get_config('vector_search.developer_whitelist', [])

        if not whitelist:
            return True

        current_user = os.environ.get('USERNAME', '').lower()
        return current_user in [u.lower() for u in whitelist]

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

        query_lower = query.lower()
        meta_triggers = [
            "what do you have access to", "what information", "what documents",
            "what standards", "list available", "available standards",
            "documents do you have", "what can you see"
        ]
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
                    'content': (
                        "The following is a complete list of all standard documents currently "
                        "indexed and available for retrieval:\n\n" + title_list +
                        "\n\nUse this list to identify which specific standards the user might be interested in."
                    ),
                    'category': 'System',
                    'score': 2.0,
                    'normalized_score': 1.0,
                    'hybrid_score': 2.0,
                    'chunk_index': 0,
                    'total_chunks': 1,
                    'last_updated': datetime.now().isoformat(),
                })

        cache_key = self._get_cache_key(query, n_results, 'hybrid')
        cached_results = self._get_cached_results(cache_key)
        if cached_results is not None:
            return cached_results

        t0_sem = time.time()
        semantic_results = self.semantic_search(query, n_results * 2)
        self._tlog("TIMING hybrid.semantic_search={:.2f}s results={}".format(
            time.time() - t0_sem, len(semantic_results)))

        t0_kw = time.time()
        keyword_results = self.keyword_search(query, n_results * 2)
        self._tlog("TIMING hybrid.keyword_search={:.2f}s results={}".format(
            time.time() - t0_kw, len(keyword_results)))

        keyword_results = self.normalize_scores(keyword_results)

        merged_map = {}

        for result in semantic_results:
            chunk_id = result['chunk_id']
            result['normalized_score'] = result['score']
            merged_map[chunk_id] = result.copy()

            title_boost = 0.0
            title_lower = result.get('title', '').lower()
            if any(term in title_lower for term in query.lower().split() if len(term) > 3):
                title_boost = 0.2
            if 'pdso' in query.lower() and 'pdso' in title_lower:
                title_boost = 0.4

            merged_map[chunk_id]['hybrid_score'] = (result['score'] + title_boost) * self.semantic_weight
            merged_map[chunk_id]['semantic_score'] = result['score'] + title_boost
            merged_map[chunk_id]['keyword_score'] = 0

        for result in keyword_results:
            chunk_id = result['chunk_id']
            if chunk_id in merged_map:
                merged_map[chunk_id]['keyword_score'] = result['normalized_score']
                merged_map[chunk_id]['hybrid_score'] += result['normalized_score'] * self.keyword_weight
            else:
                merged_map[chunk_id] = result.copy()
                merged_map[chunk_id]['hybrid_score'] = result['normalized_score'] * self.keyword_weight
                merged_map[chunk_id]['semantic_score'] = 0
                merged_map[chunk_id]['keyword_score'] = result['normalized_score']

        merged_results = list(merged_map.values())
        merged_results.sort(key=lambda x: x['hybrid_score'], reverse=True)

        for result in merged_results:
            result['score'] = result['hybrid_score']

        if deduplicate:
            merged_results = self.deduplicate_by_url(merged_results)

        final_results = synthetic_results + merged_results[:n_results]
        self._cache_results(cache_key, final_results)
        return final_results

    def get_stats(self):
        """
        Get statistics about the indexed collection.

        Returns:
            Dict with document count, chunk count, last sync time
        """
        index = self._load_index()
        if index is None:
            return {
                'total_chunks': 0,
                'unique_documents': 0,
                'last_sync': self.config.get_config('vector_search.last_sync_timestamp', None),
            }
        embeddings, metadata_list = index
        unique_doc_ids = set(m.get('doc_id', '') for m in metadata_list if m.get('doc_id'))
        return {
            'total_chunks': len(metadata_list),
            'unique_documents': len(unique_doc_ids),
            'last_sync': self.config.get_config('vector_search.last_sync_timestamp', None),
        }
