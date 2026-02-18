#! python3
"""
Search for any content about family libraries, approved families, or pre-vetted families
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
    """Search for family library content"""
    try:
        config = ConfigManager()
        vector_db = VectorDBClient(config)
        
        search_terms = [
            "approved families location",
            "family library",
            "standard families",
            "where families stored",
            "BBB families"
        ]
        
        for query in search_terms:
            print(f"\n{'=' * 80}")
            print(f"Query: {query}")
            print(f"{'=' * 80}")
            
            results = vector_db.hybrid_search(query=query, deduplicate=True)
            
            if results:
                print(f"Top 3 results:\n")
                for i, result in enumerate(results[:3]):
                    print(f"#{i+1}: {result.get('title', 'Untitled')}")
                    print(f"    Category: {result.get('category', 'Unknown')}")
                    print(f"    Score: {result.get('score', 0):.4f}")
                    content_preview = result.get('content', '')[:150].replace('\n', ' ')
                    print(f"    Preview: {content_preview}...")
                    print()
            else:
                print("No results found")
        
        return 0
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
