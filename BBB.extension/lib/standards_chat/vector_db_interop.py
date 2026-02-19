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
import tempfile
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
        
        self.python_exe = self._find_python(current_dir)
        debug_log("VectorDBInteropClient: using python: {}".format(self.python_exe))

    def _find_python(self, start_dir):
        """
        Find the best available CPython 3 executable. Resolution order:
          1. config vector_search.python_path  (explicit override)
          2. .venv relative to extension root  (dev/production venv)
          3. Windows 'py -3' launcher           (standard Python install on Windows)
          4. 'python3' / 'python'               (PATH fallback)
        """
        # 1. Explicit config override
        configured = self.config.get_config('vector_search.python_path', None)
        if configured and os.path.isfile(configured):
            debug_log("_find_python: using config path: {}".format(configured))
            return configured

        # 2. Walk up from the script dir looking for a .venv
        #    Covers: repo-root venv (dev) and extension-level venv (production)
        search_dir = start_dir
        for _ in range(6):  # max 6 levels up
            candidate = os.path.join(search_dir, '.venv', 'Scripts', 'python.exe')
            if os.path.isfile(candidate):
                debug_log("_find_python: found venv at: {}".format(candidate))
                return candidate
            parent = os.path.dirname(search_dir)
            if parent == search_dir:
                break
            search_dir = parent

        # 3. Windows 'py' launcher (present on any standard Windows Python install)
        try:
            result = subprocess.Popen(
                ['py', '-3', '-c', 'import sys; print(sys.executable)'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                shell=False, creationflags=0x08000000
            )
            out, _ = result.communicate()
            if result.returncode == 0:
                exe = out.strip()
                if isinstance(exe, bytes):
                    exe = exe.decode('utf-8', errors='replace').strip()
                if exe and os.path.isfile(exe):
                    debug_log("_find_python: found via py launcher: {}".format(exe))
                    return exe
        except Exception:
            pass

        # 4. PATH fallback
        debug_log("_find_python: falling back to 'python' in PATH")
        return 'python'

    def hybrid_search(self, query, n_results=10, deduplicate=True):
        """
        Execute hybrid search via CLI script
        """
        try:
            debug_log("VectorDBInteropClient: hybrid_search for query: {}".format(safe_str(query)[:100]))
            
            # Base64 encode query to avoid CLI encoding issues with special chars.
            # Always decode to a plain ASCII str so it is safe in a subprocess cmd list
            # regardless of whether we are running in IronPython 2.7 or CPython 3.x.
            query_bytes = query.encode('utf-8')
            raw_b64 = base64.b64encode(query_bytes)
            # raw_b64 may be bytes (CPython 3) or str (IronPython 2.7)
            if isinstance(raw_b64, bytes):
                query_b64 = raw_b64.decode('ascii')
            else:
                query_b64 = str(raw_b64)
            
            # Prepare command — use a temp file for output to avoid IronPython stdout-pipe issues
            tmp_fd, tmp_path = tempfile.mkstemp(suffix='.json', prefix='kodama_search_')
            os.close(tmp_fd)  # close the fd; the script will open it by path
            
            cmd = [self.python_exe, self.script_path, "--base64", query_b64, "--output", tmp_path]
            debug_log("VectorDBInteropClient: executing command: {} <query_b64_len={}>".format(
                ' '.join([self.python_exe, self.script_path, '--base64', '...', '--output', tmp_path]), len(query_b64)))
            
            # Use subprocess to run the command.
            # CREATE_NO_WINDOW (0x08000000) prevents a visible CMD console popping up on Windows.
            CREATE_NO_WINDOW = 0x08000000
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                shell=False,
                creationflags=CREATE_NO_WINDOW
            )
            
            stdout, stderr = process.communicate()
            debug_log("VectorDBInteropClient: process returned code {}".format(process.returncode))
            
            # Read result from temp file (more reliable than stdout pipe in IronPython)
            json_str = None
            try:
                if os.path.exists(tmp_path):
                    with open(tmp_path, 'r') as f:
                        json_str = f.read().strip()
                    os.remove(tmp_path)
            except Exception as read_err:
                debug_log("VectorDBInteropClient: failed to read temp output file: {}".format(safe_str(read_err)))
            
            if process.returncode != 0 or not json_str:
                # Decode stdout/stderr for diagnostics
                if isinstance(stdout, bytes):
                    stdout_str = stdout.decode('utf-8', errors='replace')
                else:
                    stdout_str = safe_str(stdout)
                if isinstance(stderr, bytes):
                    stderr_str = stderr.decode('utf-8', errors='replace')
                else:
                    stderr_str = safe_str(stderr)
                safe_print("Vector Search CLI Error (stdout): {}".format(stdout_str))
                safe_print("Vector Search CLI Error (stderr): {}".format(stderr_str))
                debug_log("VectorDBInteropClient: CLI stdout: {}".format(stdout_str[:1000]))
                debug_log("VectorDBInteropClient: CLI stderr: {}".format(stderr_str[:500]))
                debug_log("VectorDBInteropClient: temp file content: {}".format((json_str or '')[:500]))
                return []
                
            # Parse output from temp file
            try:
                data = json.loads(json_str)
                if data.get('success'):
                    results = data.get('results', [])
                    debug_log("VectorDBInteropClient: parsed {} results".format(len(results)))
                    return results
                else:
                    error = data.get('error', 'Unknown error')
                    tb = data.get('traceback', '')
                    safe_print("Vector Search API Error: {}".format(safe_str(error)))
                    debug_log("VectorDBInteropClient: script error: {}".format(safe_str(error)[:500]))
                    if tb:
                        debug_log("VectorDBInteropClient: traceback: {}".format(safe_str(tb)[:1000]))
                    return []
                    
            except Exception as e:
                safe_print("Error parsing vector search output: {}".format(safe_str(e)))
                safe_print("Raw output: {}".format(safe_str(json_str)))
                return []
                
        except Exception as e:
            safe_print("Failed to execute vector search CLI: {}".format(safe_str(e)))
            import traceback
            safe_print("Traceback: {}".format(traceback.format_exc()))
            return []
            
    def is_developer_mode_enabled(self):
        """Check config via CLI or just pass through (CLI checks it anyway)"""
        return True # CLI enforces this
