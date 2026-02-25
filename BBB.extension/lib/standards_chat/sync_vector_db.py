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

def main(progress_callback=None):
    """Perform SharePoint to vector DB sync"""
    try:
        # Import modules directly to avoid triggering package __init__.py
        # which tries to load IronPython dependencies (clr)
        import importlib.util
        
        # Get the standards_chat directory
        standards_chat_dir = os.path.dirname(__file__)
        
        # Load utils first (required by other modules)
        utils_spec = importlib.util.spec_from_file_location(
            "standards_chat.utils",
            os.path.join(standards_chat_dir, "utils.py")
        )
        utils_module = importlib.util.module_from_spec(utils_spec)
        sys.modules['standards_chat.utils'] = utils_module
        utils_spec.loader.exec_module(utils_module)
        
        # Load config_manager
        config_spec = importlib.util.spec_from_file_location(
            "standards_chat.config_manager", 
            os.path.join(standards_chat_dir, "config_manager.py")
        )
        config_module = importlib.util.module_from_spec(config_spec)
        sys.modules['standards_chat.config_manager'] = config_module
        config_spec.loader.exec_module(config_module)
        ConfigManager = config_module.ConfigManager
        
        # Load sharepoint_client
        sharepoint_spec = importlib.util.spec_from_file_location(
            "standards_chat.sharepoint_client",
            os.path.join(standards_chat_dir, "sharepoint_client.py")
        )
        sharepoint_module = importlib.util.module_from_spec(sharepoint_spec)
        sys.modules['standards_chat.sharepoint_client'] = sharepoint_module
        sharepoint_spec.loader.exec_module(sharepoint_module)
        SharePointClient = sharepoint_module.SharePointClient
        
        # Load vector_db_client
        vector_spec = importlib.util.spec_from_file_location(
            "standards_chat.vector_db_client",
            os.path.join(standards_chat_dir, "vector_db_client.py")
        )
        vector_module = importlib.util.module_from_spec(vector_spec)
        sys.modules['standards_chat.vector_db_client'] = vector_module
        vector_spec.loader.exec_module(vector_module)
        VectorDBClient = vector_module.VectorDBClient
        
        print("Initializing clients...")
        config_manager = ConfigManager()
        sharepoint_client = SharePointClient(config_manager)
        vector_db_client = VectorDBClient(config_manager)
        
        # Check if user is allowed
        if not vector_db_client.is_developer_mode_enabled():
            print("ERROR: Vector search is not available for your user.")
            sys.exit(1)
        
        if progress_callback is None:
            def progress_callback(message, current, total):
                """Fallback: plain text progress updates"""
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
