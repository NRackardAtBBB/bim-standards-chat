# Vector Search Feature - Developer Guide

## Overview

The vector search feature enables semantic search of SharePoint content using AI embeddings, providing more relevant results than traditional keyword matching. This is a developer-only feature controlled by username whitelist.

## Architecture

### Components

1. **VectorDBClient** (`lib/standards_chat/vector_db_client.py`)
   - ChromaDB integration for vector storage
   - OpenAI embeddings generation (`text-embedding-3-small`)
   - Text chunking (500 tokens with 100 token overlap)
   - Hybrid search (semantic + keyword with score normalization)
   - URL-based deduplication

2. **SharePointClient Extension** (`lib/standards_chat/sharepoint_client.py`)
   - `sync_to_vector_db()` method for indexing
   - Progress callback support for UI updates

3. **ChatWindow Integration** (`lib/standards_chat/chat_window.py`)
   - Automatic fallback to keyword search if vector DB unavailable
   - Transparent switching based on feature toggle

4. **Settings UI** (`lib/ui/settings_window.xaml` + `Settings.pushbutton/script.py`)
   - Developer-only visibility based on username whitelist
   - Manual sync trigger
   - Statistics display (docs indexed, chunks, last sync time)

## Configuration

### config.json

```json
{
  "features": {
    "enable_vector_search": false  // Toggle on to enable
  },
  "vector_search": {
    "developer_mode": true,  // Requires username whitelist
    "developer_whitelist": ["nrackard"],  // Add usernames here
    "embedding_provider": "openai",
    "embedding_model": "text-embedding-3-small",
    "embedding_dimensions": 1536,
    "db_path": "vector_db",  // Relative to config dir
    "chunk_size": 500,
    "chunk_overlap": 100,
    "max_results": 10,
    "similarity_threshold": 0.5,
    "hybrid_search_weight_semantic": 0.7,
    "hybrid_search_weight_keyword": 0.3,
    "last_sync_timestamp": null,  // Auto-updated
    "indexed_document_count": 0,  // Auto-updated
    "indexed_chunk_count": 0  // Auto-updated
  }
}
```

### api_keys.json (local, not committed)

Copy the template file and add your key:

1. Copy [BBB.extension/config/api_keys.example.json](BBB.extension/config/api_keys.example.json) to `BBB.extension/config/api_keys.json`
2. Update:
```json
{
   "openai_api_key": "sk-proj-YOUR_KEY_HERE"
}
```

## Installation

### Prerequisites

pyRevit can use external Python via the **cpython engine**. This requires:
1. Python 3.12.3 (64-bit) installed separately
2. Packages installed via pip into that Python
3. The `#! python3` shebang in scripts (already configured)

### Install Python and Packages

1. **Download Python 3.12.3 (64-bit):**
   - Get the Windows x86-64 executable installer from [python.org](https://www.python.org/downloads/release/python-3123/)
   - During installation, **check "Add Python to PATH"**

2. **Verify Installation:**
   ```powershell
   python --version  # Should show 3.12.3
   pip --version     # Should show pip 2x.x
   ```

3. **Install Packages:**
   ```powershell
   pip install chromadb openai tiktoken
   ```

4. **Find site-packages Path (for troubleshooting):**
   ```powershell
   python -c "import site; print(site.getsitepackages()[0])"
   ```

### Code Configuration

The [vector_db_client.py](BBB.extension/lib/standards_chat/vector_db_client.py) is already configured:
- **Shebang:** `#! python3` on line 1 triggers cpython engine
- **Path Detection:** Auto-detects site-packages (lines 13-24)

If auto-detection fails, uncomment lines 16-17 and manually set your paths.

### Setup Steps

1. **Add your username to whitelist** in [config.json](BBB.extension/config/config.json):
   ```json
   "developer_whitelist": ["nrackard", "yourusername"]
   ```

2. **Add OpenAI API key** to [api_keys.json](BBB.extension/config/api_keys.json) (create it from the example template):
   ```json
   "openai_api_key": "sk-proj-YOUR_KEY_HERE"
   ```

3. **Enable the feature** in Settings:
   - Open Kodama Settings
   - Check "Enable semantic search (Developer Preview)"
   - Click "Sync SharePoint to Vector Database"
   - Wait for sync to complete

4. **Start using semantic search** - queries will now use hybrid search automatically

## How It Works

### Indexing Process

1. Fetches all SharePoint pages via `get_all_pages_for_index()`
2. Splits each page into 500-token chunks with 100-token overlap
3. Generates OpenAI embeddings for each chunk
4. Stores in ChromaDB with metadata:
   - `title`: Page title
   - `url`: Original SharePoint URL
   - `category`: Page category
   - `chunk_index`: Position in document
   - `total_chunks`: Total chunks for this document
   - `last_updated`: Sync timestamp

### Search Process

1. **Query Embedding**: Generate embedding for user query
2. **Semantic Search**: ChromaDB cosine similarity search
3. **Keyword Search**: Text matching in metadata and content
4. **Score Normalization**: Min-max scaling to 0-1 range
5. **Hybrid Scoring**: 
   - Semantic: 70% weight
   - Keyword: 30% weight
6. **Deduplication**: Keep highest-scoring chunk per URL
7. **Return Top Results**: Ranked by hybrid score

### Integration with Existing Flow

```python
# In chat_window.py submit_message()
if self.vector_db_client is not None:
    # Use vector search
    relevant_pages = self.vector_db_client.hybrid_search(query=user_input)
else:
    # Fallback to keyword search
    relevant_pages = self.standards_client.search_standards(search_query)
```

Results are returned in the same format as keyword search, so the rest of the pipeline (LLM context building, source display) works unchanged.

## Cost Considerations

### OpenAI Embeddings Pricing (text-embedding-3-small)

- **Cost**: ~$0.02 per 1M tokens (~750,000 words)
- **Initial sync**: ~$0.003 for 45 pages (100k words estimated)
- **Per-query**: $0.0001 per search (negligible)

### Sync Frequency

- **Manual sync only** during development (Option C)
- No automatic re-syncing
- Re-sync when SharePoint content changes significantly

## Developer Mode

When `developer_mode: true`, only users in the whitelist can:
- See the "Enable semantic search" checkbox
- Access the sync button and statistics
- Use vector search in queries

Other users will automatically fall back to keyword search with no UI changes.

## Troubleshooting

### Import Errors

If you see "No module named 'chromadb'" or similar:
```bash
# Check Python environment
python --version
python -m pip list | grep chromadb

# Install in correct environment
python -m pip install chromadb openai tiktoken
```

### Sync Failures

Check [debug.log](BBB.extension/config/debug.log) for errors:
- SharePoint connection issues
- OpenAI API key problems
- File permission errors

### Search Not Using Vector DB

Verify:
1. Feature toggle enabled in config
2. Username in whitelist (case-insensitive)
3. Database initialized (check `config/vector_db/` directory)
4. Successful sync completed

## Future Enhancements

1. **Auto-sync**: Daily on first launch with timestamp check
2. **Incremental sync**: Only update changed pages
3. **Advanced chunking**: Section-aware splitting for better context
4. **Metadata filters**: Filter by category, date, etc.
5. **Relevance feedback**: Learn from user interactions
6. **Multi-lingual support**: Embeddings for other languages

## Files Modified

- [config.json](BBB.extension/config/config.json) - Added vector_search section
- [api_keys.example.json](BBB.extension/config/api_keys.example.json) - Template for local API keys
- [vector_db_client.py](BBB.extension/lib/standards_chat/vector_db_client.py) - New module
- [sharepoint_client.py](BBB.extension/lib/standards_chat/sharepoint_client.py) - Added sync_to_vector_db()
- [config_manager.py](BBB.extension/lib/standards_chat/config_manager.py) - Added get_config(), set_config(), save()
- [chat_window.py](BBB.extension/lib/standards_chat/chat_window.py) - Vector DB initialization and search integration
- [settings_window.xaml](BBB.extension/lib/ui/settings_window.xaml) - Added vector search UI
- [Settings.pushbutton/script.py](BBB.extension/Chat.tab/Kodama.panel/Settings.pushbutton/script.py) - Added event handlers
- [requirements.txt](requirements.txt) - New file with dependencies

## Contact

For issues or questions about this feature, contact the developer who added your username to the whitelist.
