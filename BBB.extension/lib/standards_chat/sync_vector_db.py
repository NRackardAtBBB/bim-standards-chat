#! python3
"""
Standalone script to sync SharePoint content to vector database.
Runs in pyRevit's bundled CPython — no pip install required.
"""
import sys
import os

# Add lib path so standards_chat package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from standards_chat.config_manager import ConfigManager
from standards_chat.sharepoint_client import SharePointClient
from standards_chat.vector_db_client import VectorDBClient


def main(progress_callback=None):
    """Perform SharePoint to vector DB sync"""
    try:
        print("Initializing clients...")
        config_manager = ConfigManager()
        sharepoint_client = SharePointClient(config_manager)
        vector_db_client = VectorDBClient(config_manager)

        if not vector_db_client.is_developer_mode_enabled():
            print("ERROR: Vector search is not available for your user.")
            sys.exit(1)

        if progress_callback is None:
            def progress_callback(message, current, total):
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
