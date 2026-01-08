"""
Sync SharePoint content to vector database for semantic search.
Run this script manually or via scheduled task to update the search index.

Usage:
    python sync_sharepoint.py
"""
import sys
import os

# Add extension lib path
script_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(script_dir, 'BBB.extension', 'lib')
sys.path.insert(0, lib_path)

# Run the sync module
from standards_chat.sync_vector_db import main

if __name__ == '__main__':
    print("=" * 60)
    print("SharePoint to Vector Database Sync")
    print("=" * 60)
    main()
