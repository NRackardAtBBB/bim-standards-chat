#! python3
"""
Check what content is actually stored for training video chunks in ChromaDB
"""

import sys
import os

# Add lib path
script_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(script_dir, 'BBB.extension', 'lib')
sys.path.insert(0, lib_path)

from standards_chat.config_manager import ConfigManager
from standards_chat.vector_db_client import VectorDBClient

def main():
    """Check video content in database"""
    try:
        print("Initializing vector database client...")
        config = ConfigManager()
        vector_db = VectorDBClient(config)
        
        print("\nSearching for training video documents...")
        
        # Get all documents from the collection
        results = vector_db.collection.get(
            where={"category": "Training Video"},
            limit=5,  # Just check first 5
            include=['metadatas', 'documents']
        )
        
        print(f"\nFound {len(results['ids'])} Training Video chunks (showing first 5)")
        print("=" * 80)
        
        for i, chunk_id in enumerate(results['ids']):
            metadata = results['metadatas'][i]
            content = results['documents'][i]
            
            print(f"\n#{i+1}: {metadata.get('title', 'Untitled')}")
            print(f"    URL: {metadata.get('url', 'No URL')}")
            print(f"    Category: {metadata.get('category', 'Unknown')}")
            print(f"    Content length: {len(content)} characters")
            print(f"    Content preview (first 200 chars):")
            print(f"    {repr(content[:200])}")
            print(f"    Chunk {metadata.get('chunk_index', 0) + 1} of {metadata.get('total_chunks', 1)}")
            print("-" * 80)
        
        return 0
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
