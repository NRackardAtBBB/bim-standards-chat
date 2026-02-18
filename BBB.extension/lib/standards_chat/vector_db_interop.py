# -*- coding: utf-8 -*-
"""
Vector DB Interop Client
Allows IronPython (Revit) to communicate with CPython Vector DB Client via CLI
"""
import sys
import os
import json
import subprocess
import base64
from standards_chat.utils import safe_print, safe_str

def debug_log(message):
    """Write debug message to log file"""
    try:
        import io
        from datetime import datetime
        log_dir = os.path.join(os.environ.get('APPDATA', ''), 'BBB', 'StandardsAssistant')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_path = os.path.join(log_dir, 'debug_log.txt')
        with io.open(log_path, 'a', encoding='utf-8') as f:
            f.write(u"{} - {}\n".format(datetime.now().isoformat(), message))
    except Exception:
        pass

class VectorDBInteropClient:
    """
    Shim client that calls search_vector_db.py via subprocess.
    Used when running in IronPython (Revit) where chromadb/openai cannot be imported directly.
    """
    
    def __init__(self, config_manager):
        self.config = config_manager
        
        # Determine path to search script
        # This file is in lib/standards_chat/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.script_path = os.path.join(current_dir, 'search_vector_db.py')
        
        # Determine python executable
        # Try to find a python 3 executable
        self.python_exe = "python" # Default to PATH
        
        # Check if we configured a specific python path
        configured_python = self.config.get_config('vector_search.python_path', None)
        if configured_python and os.path.exists(configured_python):
            self.python_exe = configured_python

    def hybrid_search(self, query, n_results=10, deduplicate=True):
        """
        Execute hybrid search via CLI script
        """
        try:
            debug_log("VectorDBInteropClient: hybrid_search for query: {}".format(safe_str(query)[:100]))
            
            # Base64 encode query to avoid CLI encoding issues with special chars
            query_bytes = query.encode('utf-8')
            query_b64 = base64.b64encode(query_bytes)
            
            # Prepare command
            cmd = [self.python_exe, self.script_path, "--base64", query_b64]
            debug_log("VectorDBInteropClient: executing command: {}".format(' '.join(cmd)))
            
            # Use subprocess to run the command
            # IronPython subprocess is slightly different than CPython, generally uses Popen
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                shell=True # Often needed in Windows/IronPython context for path resolution
            )
            
            stdout, stderr = process.communicate()
            debug_log("VectorDBInteropClient: process returned code {}".format(process.returncode))
            
            if process.returncode != 0:
                safe_print("Vector Search CLI Error: {}".format(safe_str(stderr)))
                debug_log("VectorDBInteropClient: CLI error: {}".format(safe_str(stderr)[:500]))
                return []
                
            # Parse output
            try:
                # The output might contain some noise if site-packages print things
                # Look for the last line that looks like JSON
                lines = stdout.strip().split('\n')
                json_str = lines[-1]
                
                data = json.loads(json_str)
                if data.get('success'):
                    results = data.get('results', [])
                    debug_log("VectorDBInteropClient: parsed {} results".format(len(results)))
                    return results
                else:
                    error = data.get('error', 'Unknown error')
                    safe_print("Vector Search API Error: {}".format(safe_str(error)))
                    return []
                    
            except Exception as e:
                safe_print("Error parsing vector search output: {}".format(safe_str(e)))
                safe_print("Raw output: {}".format(safe_str(stdout)))
                return []
                
        except Exception as e:
            safe_print("Failed to execute vector search CLI: {}".format(safe_str(e)))
            import traceback
            safe_print("Traceback: {}".format(traceback.format_exc()))
            return []
            
    def is_developer_mode_enabled(self):
        """Check config via CLI or just pass through (CLI checks it anyway)"""
        return True # CLI enforces this
