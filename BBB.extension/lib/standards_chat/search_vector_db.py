#! python3
# -*- coding: utf-8 -*-
"""
Vector Database Search Script
Runs in Python 3 to perform semantic search on the vector database
"""

import sys
import os
import json
import base64
import traceback

# Add lib path
script_dir = os.path.dirname(__file__)
lib_path = os.path.dirname(script_dir)
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

from standards_chat.config_manager import ConfigManager
from standards_chat.vector_db_client import VectorDBClient


def _debug_log(message):
    """Write directly to the same debug log used by the interop client."""
    try:
        import io
        from datetime import datetime
        log_dir = os.path.join(os.environ.get('APPDATA', ''), 'BBB', 'StandardsAssistant')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_path = os.path.join(log_dir, 'debug_log.txt')
        with io.open(log_path, 'a', encoding='utf-8') as f:
            f.write(u"{} [search_script] {}\n".format(datetime.now().isoformat(), message))
    except Exception:
        pass


def _write_result(result_dict, output_file=None):
    """Write JSON result to output file or stdout."""
    json_str = json.dumps(result_dict, ensure_ascii=False)
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(json_str)
    else:
        print(json_str)


def main():
    """
    Main entry point for vector search
    Accepts query as command-line argument
    Returns JSON results to stdout or --output file
    """
    output_file = None
    try:
        if len(sys.argv) < 2:
            _write_result({'success': False, 'error': 'No query provided'}, output_file)
            return 1

        # Parse arguments
        args = sys.argv[1:]
        query = None
        i = 0
        while i < len(args):
            if args[i] == '--base64' and i + 1 < len(args):
                query = base64.b64decode(args[i + 1]).decode('utf-8')
                i += 2
            elif args[i] == '--output' and i + 1 < len(args):
                output_file = args[i + 1]
                i += 2
            else:
                query = args[i]
                i += 1

        if not query:
            _write_result({'success': False, 'error': 'No query provided'}, output_file)
            return 1

        _debug_log("Starting search for query: {}".format(query[:80]))

        # Initialize clients
        config = ConfigManager()
        vector_db = VectorDBClient(config)

        # Check if vector search is enabled and user is authorized
        if not config.get_config('features.enable_vector_search', False):
            _write_result({'success': False, 'error': 'Vector search is disabled'}, output_file)
            return 1

        if not vector_db.is_developer_mode_enabled():
            _write_result({'success': False, 'error': 'User not authorized for vector search'}, output_file)
            return 1

        # Perform hybrid search
        results = vector_db.hybrid_search(query=query, deduplicate=True)

        _debug_log("Search complete: {} results".format(len(results)))

        _write_result({'success': True, 'results': results}, output_file)
        return 0

    except Exception as e:
        tb = traceback.format_exc()
        _debug_log("EXCEPTION: {}\n{}".format(str(e), tb))
        _write_result({'success': False, 'error': str(e), 'traceback': tb}, output_file)
        return 1


if __name__ == '__main__':
    sys.exit(main())

