#! python3
# -*- coding: utf-8 -*-
"""
Vector Database Search Script
Runs in Python 3 to perform semantic search on the vector database
"""

import sys
import os
import json

# Add lib path
script_dir = os.path.dirname(__file__)
lib_path = os.path.dirname(script_dir)
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

from standards_chat.config_manager import ConfigManager
from standards_chat.vector_db_client import VectorDBClient


def main():
    """
    Main entry point for vector search
    Accepts query as command-line argument
    Returns JSON results to stdout
    """
    try:
        if len(sys.argv) < 2:
            print(json.dumps({
                'success': False,
                'error': 'No query provided'
            }))
            return 1
        
        query = sys.argv[1]
        
        # Initialize clients
        config = ConfigManager()
        vector_db = VectorDBClient(config)
        
        # Check if vector search is enabled and user is authorized
        if not config.get_config('features.enable_vector_search', False):
            print(json.dumps({
                'success': False,
                'error': 'Vector search is disabled'
            }))
            return 1
        
        if not vector_db.is_developer_mode_enabled():
            print(json.dumps({
                'success': False,
                'error': 'User not authorized for vector search'
            }))
            return 1
        
        # Perform hybrid search
        results = vector_db.hybrid_search(
            query=query,
            deduplicate=True
        )
        
        # Return results as JSON (ensure_ascii=False to properly encode Unicode)
        print(json.dumps({
            'success': True,
            'results': results
        }, ensure_ascii=False))
        return 0
        
    except Exception as e:
        print(json.dumps({
            'success': False,
            'error': str(e)
        }))
        return 1


if __name__ == '__main__':
    sys.exit(main())
