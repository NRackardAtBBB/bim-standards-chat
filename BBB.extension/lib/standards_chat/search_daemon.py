#! python3
# -*- coding: utf-8 -*-
"""
Kodama Vector Search Daemon
===========================
A lightweight HTTP server that keeps VectorDBClient warm between queries so
that the per-query cost of:
  - Python process startup + heavy package imports  (~44 s)
  - chromadb.PersistentClient initialisation         (~14 s)
is paid only ONCE (at daemon start), not on every query.

Lifecycle
---------
* The IronPython interop client starts this daemon the first time a search is
  needed, then reuses it for all subsequent searches in the same Revit session.
* The daemon writes its PID and HTTP port to a state file so the interop client
  can find it across code reloads.
* The daemon shuts itself down automatically after IDLE_TIMEOUT_SECONDS of
  inactivity so it never leaks across long sessions.

Communication
-------------
POST /search   body: {"query": "...", "n_results": 10, "deduplicate": true}
               resp: {"success": true, "results": [...]}

POST /shutdown  â†’ graceful shutdown (used by interop client on Revit exit)
GET  /ping      â†’ {"ok": true}  (readiness probe)
"""

import sys
import os
import json
import time
import threading
import socket
import traceback
import signal

# ---------------------------------------------------------------------------
# Path setup â€“ support being called directly from disk
# ---------------------------------------------------------------------------
_script_dir = os.path.dirname(os.path.abspath(__file__))
_lib_path = os.path.dirname(_script_dir)
if _lib_path not in sys.path:
    sys.path.insert(0, _lib_path)

# ---------------------------------------------------------------------------
# Shared debug log
# ---------------------------------------------------------------------------
def _dlog(message):
    try:
        import io
        from datetime import datetime
        log_dir = os.path.join(os.environ.get('APPDATA', ''), 'BBB', 'StandardsAssistant')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_path = os.path.join(log_dir, 'debug_log.txt')
        with io.open(log_path, 'a', encoding='utf-8') as f:
            f.write(u"{} [daemon] {}\n".format(datetime.now().isoformat(), message))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# State-file helpers (shared between daemon and interop client)
# ---------------------------------------------------------------------------
STATE_DIR = os.path.join(
    os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
    'BBB', 'Kodama'
)
STATE_FILE = os.path.join(STATE_DIR, 'daemon_state.json')


def write_state(pid, port):
    try:
        if not os.path.exists(STATE_DIR):
            os.makedirs(STATE_DIR)
        with open(STATE_FILE, 'w') as f:
            json.dump({'pid': pid, 'port': port, 'started': time.time()}, f)
    except Exception as e:
        _dlog("write_state failed: {}".format(e))


def read_state():
    """Return (pid, port) or (None, None) if state file is absent or corrupt."""
    try:
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
        return data.get('pid'), data.get('port')
    except Exception:
        return None, None


def clear_state():
    try:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
    except Exception:
        pass


def is_pid_alive(pid):
    """Return True if a process with *pid* is currently running."""
    if pid is None:
        return False
    try:
        # os.kill(pid, 0) raises OSError if the process doesn't exist
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
from typing import Any

try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
except ImportError as _e:
    raise RuntimeError("search_daemon.py requires Python 3 (http.server not found): {}".format(_e))


class _SearchHandler(BaseHTTPRequestHandler):
    """Request handler â€“ shares VectorDBClient via server.db_client."""

    # Silence the default request log to stdout (we use our own debug log)
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length:
            return self.rfile.read(length)
        return b''

    def do_GET(self):
        server: Any = self.server
        if self.path == '/ping':
            server._reset_idle_timer()
            self._send_json(200, {'ok': True})
        else:
            self._send_json(404, {'error': 'not found'})

    def do_POST(self):
        if self.path == '/search':
            self._handle_search()
        elif self.path == '/shutdown':
            self._send_json(200, {'ok': True})
            # Shut down in a background thread so the response is sent first
            server: Any = self.server
            t = threading.Thread(target=server.shutdown_gracefully)
            t.daemon = True
            t.start()
        else:
            self._send_json(404, {'error': 'not found'})

    def _handle_search(self):
        server: Any = self.server
        server._reset_idle_timer()
        try:
            raw = self._read_body()
            req = json.loads(raw.decode('utf-8'))
            query = req.get('query', '')
            n_results = int(req.get('n_results', 10))
            deduplicate = bool(req.get('deduplicate', True))

            if not query:
                self._send_json(400, {'success': False, 'error': 'query is required'})
                return

            t0 = time.time()
            _dlog("daemon: search start query='{}'".format(query[:80]))

            db = server.db_client
            results = db.hybrid_search(query=query, n_results=n_results, deduplicate=deduplicate)

            elapsed = time.time() - t0
            _dlog("daemon: search done elapsed={:.2f}s results={}".format(elapsed, len(results)))

            self._send_json(200, {'success': True, 'results': results})

        except Exception as e:
            tb = traceback.format_exc()
            _dlog("daemon: search exception: {}\n{}".format(e, tb))
            self._send_json(500, {'success': False, 'error': str(e), 'traceback': tb})


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
IDLE_TIMEOUT_SECONDS = 1800  # 30 minutes


class _SearchServer(HTTPServer):
    def __init__(self, server_address, db_client):
        HTTPServer.__init__(self, server_address, _SearchHandler)
        self.db_client = db_client
        self._idle_timer = None
        self._reset_idle_timer()

    def _reset_idle_timer(self):
        if self._idle_timer is not None:
            self._idle_timer.cancel()
        self._idle_timer = threading.Timer(IDLE_TIMEOUT_SECONDS, self.shutdown_gracefully)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def shutdown_gracefully(self):
        _dlog("daemon: shutting down (idle timeout or explicit request)")
        clear_state()
        # HTTPServer.shutdown() must be called from a different thread
        t = threading.Thread(target=self.shutdown)
        t.daemon = True
        t.start()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    _dlog("daemon: starting up (PID={})".format(os.getpid()))

    # Import heavy packages here; this is the one-time startup cost
    t0_init = time.time()
    try:
        from standards_chat.config_manager import ConfigManager
        from standards_chat.vector_db_client import VectorDBClient
    except Exception as e:
        _dlog("daemon: import failed: {}".format(e))
        sys.exit(1)

    try:
        config = ConfigManager()
        db_client = VectorDBClient(config)
    except Exception as e:
        _dlog("daemon: VectorDBClient init failed: {}\n{}".format(e, traceback.format_exc()))
        sys.exit(2)

    init_elapsed = time.time() - t0_init
    _dlog("daemon: VectorDBClient ready in {:.2f}s".format(init_elapsed))

    # Bind to a random available localhost port
    server = _SearchServer(('127.0.0.1', 0), db_client)
    port = server.server_address[1]

    write_state(os.getpid(), port)
    _dlog("daemon: listening on 127.0.0.1:{} (idle timeout={}s)".format(port, IDLE_TIMEOUT_SECONDS))

    # Signal readiness to the interop client by printing the port to stdout
    # (interop client waits for this line then reads the state file)
    sys.stdout.write("DAEMON_READY port={}\n".format(port))
    sys.stdout.flush()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        clear_state()
        _dlog("daemon: exited cleanly")


if __name__ == '__main__':
    main()
