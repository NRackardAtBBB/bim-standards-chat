# -*- coding: utf-8 -*-
"""
Vector DB Interop Client
Allows IronPython (Revit) to communicate with CPython Vector DB Client.

Uses pyRevit's bundled CPython — no pip install required.
IronPython calls pyRevit CPython as a one-shot subprocess to do numpy
cosine similarity math and return JSON results.
"""
import sys
import os
import json
import subprocess
import base64
import tempfile
import time
import threading as _threading

from standards_chat.utils import safe_print, safe_str


# ---------------------------------------------------------------------------
# Shared debug log
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Local cache paths (used for DB copy from network → local)
# ---------------------------------------------------------------------------
_STATE_DIR = os.path.join(
    os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
    'BBB', 'Kodama'
)


# ---------------------------------------------------------------------------
# Find pyRevit's bundled CPython
# ---------------------------------------------------------------------------
def _find_pyrevit_cpython():
    """
    Locate pyRevit's bundled CPython executable.

    Resolution order:
      1. Known pyRevit cengines directories (all install locations, CPY312 preferred)
      2. Windows 'py -3' launcher
      3. 'python' on PATH

    Returns the path string; raises RuntimeError if nothing is found.
    """
    _appdata  = os.environ.get('APPDATA', '')
    _localapp = os.environ.get('LOCALAPPDATA', '')

    _engine_roots = [
        os.path.join(_appdata,  'pyRevit-Master', 'bin', 'cengines'),
        os.path.join(_appdata,  'pyRevit',         'bin', 'cengines'),
        os.path.join(_localapp, 'pyRevit-Master',  'bin', 'cengines'),
        os.path.join(_localapp, 'pyRevit',          'bin', 'cengines'),
        r'C:\ProgramData\pyRevit\bin\cengines',
    ]
    _preferred = ['CPY312', 'CPY311', 'CPY310', 'CPY313', 'CPY3']

    def _priority(name):
        for idx, prefix in enumerate(_preferred):
            if name.upper().startswith(prefix):
                return idx
        return 99

    for root in _engine_roots:
        if not os.path.isdir(root):
            continue
        for eng in sorted(os.listdir(root), key=_priority):
            if not eng.upper().startswith('CPY3'):
                continue
            exe = os.path.join(root, eng, 'python.exe')
            if os.path.isfile(exe):
                debug_log('_find_pyrevit_cpython: found {}'.format(exe))
                return exe

    # Verify numpy is available before committing to a PATH python
    for candidate_cmd in (['py', '-3'], ['python3'], ['python']):
        try:
            r = subprocess.Popen(
                candidate_cmd + ['-c', 'import numpy; print("ok")'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                shell=False, creationflags=0x08000000
            )
            out, _ = r.communicate()
            if isinstance(out, bytes):
                out = out.decode('utf-8', errors='replace')
            if r.returncode == 0 and 'ok' in out:
                debug_log('_find_pyrevit_cpython: using PATH python: {}'.format(candidate_cmd[0]))
                return candidate_cmd[0]
        except Exception:
            pass

    raise RuntimeError(
        "pyRevit CPython not found. Make sure pyRevit is installed.\n"
        "Checked: {}".format([r for r in _engine_roots])
    )


# Resolved once at import time; cached module-level
try:
    _PYREVIT_PYTHON = _find_pyrevit_cpython()
    debug_log('vector_db_interop: using Python: {}'.format(_PYREVIT_PYTHON))
except RuntimeError as _e:
    _PYREVIT_PYTHON = None
    debug_log('vector_db_interop: WARNING – could not find CPython: {}'.format(_e))


# ---------------------------------------------------------------------------
# DB sync status (used by script.py and db_update_window.py)
# ---------------------------------------------------------------------------
_db_sync_status = {
    'phase':      'idle',   # 'idle' | 'syncing' | 'done' | 'error'
    'message':    u'',
    'error':      None,
    'start_time': None,
}


def check_db_needs_update(config_manager):
    """
    Return True if the network vector DB is newer than the local cache,
    or if no local cache exists yet.  Returns False on any error (fail-safe).
    """
    try:
        db_path_rel = config_manager.get_config('vector_search.db_path', 'vector_db')
        lib_dir     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir  = os.path.join(lib_dir, 'config')
        network_db_path    = os.path.join(config_dir, db_path_rel)
        network_sentinel   = os.path.join(network_db_path, 'vectors.npz')

        if not os.path.exists(network_sentinel):
            return False   # nothing on the network to sync

        local_db_path    = os.path.join(_STATE_DIR, 'vector_db')
        local_sentinel   = os.path.join(local_db_path, 'vectors.npz')

        if not os.path.exists(local_sentinel):
            return True   # no local copy at all

        return os.path.getmtime(network_sentinel) > os.path.getmtime(local_sentinel)

    except Exception as exc:
        debug_log('check_db_needs_update error: {}'.format(exc))
        return False


def start_db_sync_async(config_manager):
    """
    Start a background thread that copies vectors.npz + metadata.json
    from the network path to the local cache directory.
    Progress is written to the module-level ``_db_sync_status`` dict.
    """
    import shutil as _shutil

    try:
        db_path_rel     = config_manager.get_config('vector_search.db_path', 'vector_db')
        lib_dir         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir      = os.path.join(lib_dir, 'config')
        network_db_path = os.path.join(config_dir, db_path_rel)
        local_db_path   = os.path.join(_STATE_DIR, 'vector_db')
    except Exception as exc:
        _db_sync_status['phase'] = 'error'
        _db_sync_status['error'] = u'Could not resolve DB paths: {}'.format(exc)
        return

    def _worker():
        _db_sync_status['phase']      = 'syncing'
        _db_sync_status['message']    = u'Copying updated standards database\u2026'
        _db_sync_status['error']      = None
        _db_sync_status['start_time'] = time.time()
        try:
            if not os.path.exists(local_db_path):
                os.makedirs(local_db_path)

            for filename in ('vectors.npz', 'metadata.json'):
                src = os.path.join(network_db_path, filename)
                dst = os.path.join(local_db_path, filename)
                if os.path.exists(src):
                    _shutil.copy2(src, dst)

            elapsed = time.time() - _db_sync_status['start_time']
            debug_log('DB sync complete in {:.1f}s'.format(elapsed))
            _db_sync_status['phase']   = 'done'
            _db_sync_status['message'] = u'Standards database updated successfully.'
        except Exception as exc:
            debug_log('DB sync error: {}'.format(exc))
            _db_sync_status['phase'] = 'error'
            _db_sync_status['error'] = u'{}'.format(exc)

    t = _threading.Thread(target=_worker, name='kodama-db-sync')
    t.daemon = True
    t.start()


def get_local_env_status():
    """Return status info about the Python environment."""
    if _PYREVIT_PYTHON:
        return {
            'status':  'ready',
            'python':  _PYREVIT_PYTHON,
            'message': u'Using pyRevit CPython \u2014 no setup required.',
        }
    return {
        'status':  'error',
        'python':  None,
        'message': u'pyRevit CPython not found. Check pyRevit installation.',
    }


def reset_local_env(rebuild=False):
    """No-op: there is no local venv to reset."""
    return True, u'Nothing to reset \u2014 no local environment is managed.'


# ---------------------------------------------------------------------------
# Main interop client
# ---------------------------------------------------------------------------
class VectorDBInteropClient:
    """
    Shim client: called from IronPython (Revit), delegates search to
    pyRevit's bundled CPython via a one-shot subprocess.
    """

    def __init__(self, config_manager):
        self.config = config_manager

        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.script_path = os.path.join(current_dir, 'search_vector_db.py')

        if _PYREVIT_PYTHON is None:
            raise RuntimeError(
                "pyRevit CPython not found — vector search unavailable.\n"
                "Make sure pyRevit is installed."
            )
        self.python_exe = _PYREVIT_PYTHON
        debug_log("VectorDBInteropClient: using python: {}".format(self.python_exe))

    def is_developer_mode_enabled(self):
        """Check if current user is authorised for vector search."""
        try:
            developer_mode = self.config.get_config('vector_search.developer_mode', True)
            if not developer_mode:
                return True
            whitelist = self.config.api_keys.get('admin_whitelist', None)
            if whitelist is None:
                whitelist = self.config.get_config('vector_search.developer_whitelist', [])
            if not whitelist:
                return True
            current_user = os.environ.get('USERNAME', '').lower()
            return current_user in [u.lower() for u in whitelist]
        except Exception:
            return True

    def hybrid_search(self, query, n_results=10, deduplicate=True):
        """Execute hybrid search via CPython subprocess."""
        debug_log("VectorDBInteropClient: hybrid_search for query: {}".format(
            safe_str(query)[:100]))
        return self._hybrid_search_cli(query, n_results, deduplicate)

    def _hybrid_search_cli(self, query, n_results=10, deduplicate=True):
        """One-shot subprocess search."""
        try:
            query_bytes = query.encode('utf-8')
            raw_b64 = base64.b64encode(query_bytes)
            if isinstance(raw_b64, bytes):
                query_b64 = raw_b64.decode('ascii')
            else:
                query_b64 = str(raw_b64)

            tmp_fd, tmp_path = tempfile.mkstemp(suffix='.json', prefix='kodama_search_')
            os.close(tmp_fd)

            cmd = [self.python_exe, self.script_path,
                   '--base64', query_b64, '--output', tmp_path]
            debug_log("VectorDBInteropClient: running subprocess (query_b64_len={})".format(
                len(query_b64)))

            CREATE_NO_WINDOW = 0x08000000
            t0 = time.time()
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                creationflags=CREATE_NO_WINDOW
            )
            stdout, stderr = process.communicate()
            debug_log("TIMING subprocess total={:.2f}s returncode={}".format(
                time.time() - t0, process.returncode))

            # Read result from temp file
            json_str = None
            try:
                import io
                with io.open(tmp_path, 'r', encoding='utf-8') as f:
                    json_str = f.read()
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

            if not json_str:
                if isinstance(stdout, bytes):
                    stdout = stdout.decode('utf-8', errors='replace')
                json_str = stdout.strip()

            if not json_str:
                if process.returncode != 0:
                    if isinstance(stderr, bytes):
                        stderr = stderr.decode('utf-8', errors='replace')
                    debug_log("subprocess stderr: {}".format(stderr[:500]))
                return []

            result = json.loads(json_str)
            if result.get('success'):
                results = result.get('results', [])
                debug_log("hybrid_search: subprocess returned {} results".format(len(results)))
                return results
            else:
                debug_log("hybrid_search: subprocess error: {}".format(
                    safe_str(result.get('error', ''))[:300]))
                return []

        except Exception as e:
            debug_log("hybrid_search CLI error: {}".format(e))
            return []
