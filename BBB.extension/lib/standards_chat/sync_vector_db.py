#! python3
"""
Standalone script to sync SharePoint content to vector database.
This runs in Python 3 (not IronPython) to access chromadb/openai/tiktoken.
"""
import sys
import os
import json

# Add lib path
script_dir = os.path.dirname(__file__)
lib_path = os.path.dirname(script_dir)
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

# Auto-detect site-packages if Python is in PATH
try:
    import site
    for path in site.getsitepackages():
        if path not in sys.path:
            sys.path.append(path)
except:
    pass

def main():
    """Perform SharePoint to vector DB sync"""
    try:
        from standards_chat.config_manager import ConfigManager
        from standards_chat.sharepoint_client import SharePointClient
        from standards_chat.vector_db_client import VectorDBClient
        
        print("Initializing clients...")
        config_manager = ConfigManager()
        sharepoint_client = SharePointClient(config_manager)
        vector_db_client = VectorDBClient(config_manager)
        
        # Check if user is allowed
        if not vector_db_client.is_developer_mode_enabled():
            print("ERROR: Vector search is not available for your user.")
            sys.exit(1)
        
        def progress_callback(message, current, total):
            """Print progress updates"""
            print("PROGRESS: {}".format(message))
        
        print("Starting sync...")
        result = sharepoint_client.sync_to_vector_db(
            vector_db_client,
            progress_callback=progress_callback
        )
        
        if result.get('success'):
            print("SUCCESS: {} documents, {} chunks".format(
                result['documents'],
                result['chunks']
            ))
            sys.exit(0)
        else:
            print("ERROR: {}".format(result.get('error', 'Unknown error')))
            sys.exit(1)
            
    except Exception as e:
        print("ERROR: {}".format(str(e)))
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
