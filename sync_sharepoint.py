"""
Sync SharePoint content to vector database for semantic search.
Run this script manually or via scheduled task to update the search index.

Usage:
    python sync_sharepoint.py
"""
import sys
import os
import importlib.util

# Add extension lib path
script_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(script_dir, 'BBB.extension', 'lib')
sys.path.insert(0, lib_path)

# Import sync module directly without triggering package __init__.py
# This avoids loading IronPython dependencies (clr) that don't work in regular Python
sync_module_path = os.path.join(lib_path, 'standards_chat', 'sync_vector_db.py')
spec = importlib.util.spec_from_file_location("sync_vector_db", sync_module_path)
sync_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_module)

if __name__ == '__main__':
    print("=" * 60)
    print("SharePoint to Vector Database Sync")
    print("=" * 60)
    sync_module.main()
