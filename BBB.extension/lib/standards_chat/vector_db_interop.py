# -*- coding: utf-8 -*-
"""
Vector DB Interop Client
Allows IronPython (Revit) to communicate with CPython Vector DB Client.

Strategy (fastest first, automatic fallback):
  1. Daemon mode  – reuse a persistent search_daemon.py process via HTTP.
     The daemon holds VectorDBClient warm, so per-query cost is < 1 s after
     first startup (which takes ~25 s but happens only once per Revit session).
  2. CLI mode     – fall back to the original one-shot subprocess approach if
     the daemon cannot be started or becomes unresponsive.
"""
import sys
import os
import json
import subprocess
import base64
import tempfile
import time
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
# Daemon state-file helpers (duplicated from search_daemon.py to avoid import)
# ---------------------------------------------------------------------------
_STATE_DIR = os.path.join(
    os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
    'BBB', 'Kodama'
)
_STATE_FILE = os.path.join(_STATE_DIR, 'daemon_state.json')

# ---------------------------------------------------------------------------
# Local venv constants
# ---------------------------------------------------------------------------
# A venv on local disk so Python imports don't cross the network on every query.
# Created automatically in the background the first time the plugin loads on a
# machine that doesn't already have one.
_LOCAL_VENV_DIR    = os.path.join(_STATE_DIR, 'venv')
_LOCAL_VENV_PYTHON = os.path.join(_LOCAL_VENV_DIR, 'Scripts', 'python.exe')
_LOCAL_VENV_LOCK   = os.path.join(_STATE_DIR, 'venv_setup.lock')
_REQUIRED_PACKAGES = ['chromadb', 'openai', 'tiktoken']

# Shared status dict written by the background setup thread and polled by the
# toast window's DispatcherTimer (both access it from different threads; dict
# assignment is GIL-atomic in CPython and IronPython, so no lock needed).
_setup_status = {'phase': 'idle', 'message': '', 'error': None, 'start_time': None}

# The currently-running setup subprocess (Popen object or None).
# Written by the background thread; read by reset_local_env to kill it on demand.
_setup_proc = None


def _read_daemon_state():
    """Return (pid, port) or (None, None)."""
    try:
        with open(_STATE_FILE, 'r') as f:
            data = json.load(f)
        return data.get('pid'), data.get('port')
    except Exception:
        return None, None


def _kill_daemon_if_running():
    """
    Kill the daemon process (if any) so it releases file handles on .pyd files
    inside the venv before we try to delete or overwrite them.
    Returns True if a process was killed.
    """
    pid, _port = _read_daemon_state()
    if pid is None:
        return False
    try:
        subprocess.call(
            ['taskkill', '/F', '/T', '/PID', str(pid)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=0x08000000
        )
        debug_log('_kill_daemon_if_running: killed daemon PID {}'.format(pid))
        # Remove state file so the next query starts a fresh daemon
        try:
            os.remove(_STATE_FILE)
        except Exception:
            pass
        return True
    except Exception as exc:
        debug_log('_kill_daemon_if_running: could not kill PID {}: {}'.format(pid, exc))
        return False


def _is_pid_alive(pid):
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        # os.kill raises OSError on CPython and various .NET exceptions on
        # IronPython (e.g. System.InvalidOperationException: "Process with an
        # Id of X is not running").  Any exception means the process is gone.
        pass
    # Secondary check via tasklist for cases where os.kill isn't available
    try:
        out = subprocess.check_output(
            ['tasklist', '/FI', 'PID eq {}'.format(pid), '/NH'],
            stderr=subprocess.PIPE, creationflags=0x08000000
        )
        if isinstance(out, bytes):
            out = out.decode('utf-8', errors='replace')
        return str(pid) in out
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Minimal HTTP client that works in IronPython 2.7 *and* CPython 3
# ---------------------------------------------------------------------------
def _http_post(port, path, payload_dict, timeout=5):
    """
    POST JSON to localhost:<port><path>.
    Returns parsed response dict or raises an exception.
    """
    body = json.dumps(payload_dict).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'Content-Length': str(len(body)),
    }
    url = 'http://127.0.0.1:{}{}'.format(port, path)

    # Try urllib.request (CPython 3), then urllib2 (IronPython 2.7)
    try:
        import urllib.request as _urlreq
        req = _urlreq.Request(url, data=body, headers=headers)
        with _urlreq.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except ImportError:
        import urllib2 as _urlreq2  # IronPython fallback
        req = _urlreq2.Request(url, data=body, headers=headers)
        resp = _urlreq2.urlopen(req, timeout=timeout)
        raw = resp.read()

    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    return json.loads(raw)


def _http_get(port, path, timeout=3):
    url = 'http://127.0.0.1:{}{}'.format(port, path)
    try:
        import urllib.request as _urlreq
        with _urlreq.urlopen(url, timeout=timeout) as resp:
            raw = resp.read()
    except ImportError:
        import urllib2 as _urlreq2
        resp = _urlreq2.urlopen(url, timeout=timeout)
        raw = resp.read()
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Main interop client
# ---------------------------------------------------------------------------
class VectorDBInteropClient:
    """
    Shim client that communicates with CPython from IronPython (Revit).

    Primary path:  daemon mode  – HTTP to a persistent search_daemon.py process.
    Fallback path: CLI mode     – one-shot subprocess (original behaviour).
    """

    # How long to wait for the daemon to become ready after starting it
    DAEMON_START_TIMEOUT = 45   # seconds
    # Maximum time to wait for a single HTTP search request
    DAEMON_REQUEST_TIMEOUT = 30  # seconds

    def __init__(self, config_manager):
        self.config = config_manager

        # Resolve paths (this file lives in lib/standards_chat/)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.script_path = os.path.join(current_dir, 'search_vector_db.py')
        self.daemon_script_path = os.path.join(current_dir, 'search_daemon.py')

        self.python_exe = self._find_python(current_dir)
        debug_log("VectorDBInteropClient: using python: {}".format(self.python_exe))

        # Bootstrap python: used ONLY for 'python -m venv' when creating the
        # local venv.  We deliberately prefer a fast locally-installed Python
        # (py launcher, PATH python) over the network-drive configured venv so
        # that venv creation doesn't itself take 40+ seconds.
        # Returns a list prefix, e.g. ['py.exe', '-3'] or ['C:\Python313\python.exe']
        self._bootstrap_cmd_prefix = self._find_bootstrap_python(current_dir)
        debug_log("VectorDBInteropClient: bootstrap cmd: {}".format(self._bootstrap_cmd_prefix))

        # Cached daemon port; None means we haven't confirmed a live daemon yet
        self._daemon_port = None

        # Ensure the local venv exists (no-op if already valid, background if not).
        venv_needs_setup = not self._local_venv_is_valid()
        self._ensure_local_venv_async()

        # Only pre-warm the daemon if the venv is already healthy.
        # If setup is running, the daemon will be started by _create_local_venv
        # after it finishes — starting it now would lock .pyd files mid-install.
        if not venv_needs_setup:
            self._prewarm_daemon()

    # ------------------------------------------------------------------
    # Local venv self-setup
    # ------------------------------------------------------------------

    @staticmethod
    def _local_venv_is_valid():
        """
        Return True if the local venv exists and all required packages import
        successfully.  Uses a quick subprocess check so IronPython can call this
        without needing the packages itself.
        """
        if not os.path.isfile(_LOCAL_VENV_PYTHON):
            return False
        try:
            result = subprocess.Popen(
                [_LOCAL_VENV_PYTHON, '-c',
                 'import chromadb, openai, tiktoken; print("ok")'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                shell=False, creationflags=0x08000000
            )
            out, _ = result.communicate()   # no timeout= — IronPython 2.7 compat
            if isinstance(out, bytes):
                out = out.decode('utf-8', errors='replace')
            return result.returncode == 0 and 'ok' in out
        except Exception:
            return False

    def _ensure_local_venv_async(self):
        """
        If the local venv is missing or broken, kick off a background thread to
        create it.  Safe to call on every startup — it's a no-op if already valid.
        """
        if self._local_venv_is_valid():
            debug_log("venv-setup: local venv already valid, skipping setup")
            return
        try:
            import threading as _threading
            # Reset shared status so the window starts fresh
            _setup_status['phase']      = 'running'
            _setup_status['message']    = u'Getting things ready for the first time\u2026'
            _setup_status['error']      = None
            _setup_status['start_time'] = time.time()

            # Show the toast on the UI thread (we are already on it here)
            self._show_setup_toast()

            t = _threading.Thread(
                target=self._create_local_venv,
                name='kodama-venv-setup'
            )
            t.daemon = True
            t.start()
            debug_log(u"venv-setup: local venv not found \u2014 background setup started")
        except Exception as e:
            debug_log("venv-setup: failed to start setup thread: {}".format(e))

    def _show_setup_toast(self):
        """Instantiate and show the setup progress toast window (UI thread only)."""
        try:
            from standards_chat.setup_progress_window import SetupProgressWindow
            toast = SetupProgressWindow(_setup_status)
            # Keep a reference so it isn't garbage-collected
            self._setup_toast = toast
            toast.Show()
        except Exception as e:
            import traceback as _tb
            debug_log("venv-setup: could not show progress window: {}\n{}".format(
                e, _tb.format_exc()))

    def _create_local_venv(self):
        """
        Create a CPython venv at *_LOCAL_VENV_DIR* and install the required
        packages.  Uses a lock file so only one Revit instance runs setup at a
        time.  Logs all progress to the shared debug log.
        """
        import io

        # ── Lock ────────────────────────────────────────────────────────
        my_pid = str(os.getpid())
        try:
            if not os.path.exists(_STATE_DIR):
                os.makedirs(_STATE_DIR)
            # Check if another instance is already running setup
            if os.path.exists(_LOCAL_VENV_LOCK):
                try:
                    with io.open(_LOCAL_VENV_LOCK, 'r') as lf:
                        lock_pid = lf.read().strip()
                    if lock_pid and _is_pid_alive(
                            int(lock_pid) if lock_pid.isdigit() else None):
                        debug_log(
                            'venv-setup: setup already running in PID {}, skipping'
                            .format(lock_pid))
                        return
                    # Stale lock — fall through and overwrite it
                    debug_log('venv-setup: stale lock (PID {}), overwriting'.format(lock_pid))
                except Exception as lock_err:
                    # Unreadable lock — treat as stale and proceed
                    debug_log('venv-setup: could not read lock, treating as stale: {}'.format(lock_err))
            with io.open(_LOCAL_VENV_LOCK, 'w') as lf:
                lf.write(my_pid)
        except Exception as e:
            debug_log('venv-setup: could not acquire lock: {} — proceeding anyway'.format(e))
            # Do NOT return here; a lock failure shouldn't prevent setup

        try:
            t0 = time.time()

            # ── Create venv ─────────────────────────────────────────────
            _setup_status['message'] = u'Getting things ready for the first time\u2026'
            debug_log("venv-setup: bootstrap cmd: {}".format(self._bootstrap_cmd_prefix))
            debug_log("venv-setup: creating venv at {}".format(_LOCAL_VENV_DIR))
            # Kill any running daemon first — it may hold .pyd file handles
            # inside the old venv, causing WinError 5 (Access Denied) on rmtree.
            _kill_daemon_if_running()
            time.sleep(1)  # give Windows a moment to release handles

            _pip_sentinel = os.path.join(_LOCAL_VENV_DIR, "pip_succeeded")
            # If pip succeeded in a previous session but imports still fail,
            # Defender is likely still scanning .pyd files. Skip rebuild.
            if os.path.exists(_LOCAL_VENV_DIR) and os.path.exists(_pip_sentinel):
                debug_log("venv-setup: pip_succeeded sentinel found -- checking if Defender scan is done")
                if self._local_venv_is_valid():
                    debug_log("venv-setup: imports now verified -- venv healthy")
                    self._python_path = _LOCAL_VENV_PYTHON
                    _setup_status["phase"]   = "daemon_starting"
                    _setup_status["message"] = u"Starting search engine\u2026"
                    self._prewarm_daemon()
                else:
                    debug_log("venv-setup: imports still failing -- leaving venv, retry next load")
                    _setup_status["message"] = u"Almost ready \u2014 restart Revit to finish setup"
                    _setup_status["phase"] = "done"
                return

            if os.path.exists(_LOCAL_VENV_DIR):
                import shutil
                shutil.rmtree(_LOCAL_VENV_DIR, ignore_errors=True)
                # Verify the directory is actually gone
                if os.path.exists(_LOCAL_VENV_DIR):
                    debug_log('venv-setup: old venv dir still present after rmtree (files locked?), waiting 3s')
                    time.sleep(3)
                    shutil.rmtree(_LOCAL_VENV_DIR, ignore_errors=True)

            venv_cmd = self._bootstrap_cmd_prefix + ['-m', 'venv', _LOCAL_VENV_DIR]
            result = subprocess.Popen(
                venv_cmd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                shell=False, creationflags=0x08000000
            )
            global _setup_proc
            _setup_proc = result
            # Poll instead of communicate() — avoids blocking forever on pipe
            # buffers and allows reset_local_env to kill us mid-flight.
            while result.poll() is None:
                _setup_status['message'] = u'Getting things ready for the first time\u2026'
                time.sleep(1)
            out, err = result.communicate()  # collect any remaining output
            _setup_proc = None
            if result.returncode != 0:
                err_str = err.decode('utf-8', errors='replace') if isinstance(err, bytes) else str(err)
                debug_log("venv-setup: venv creation FAILED: {}".format(err_str[:500]))
                _setup_status['error'] = 'venv creation failed'
                _setup_status['phase'] = 'error'
                return
            debug_log("venv-setup: venv created in {:.1f}s".format(time.time() - t0))

            # ── Install packages ────────────────────────────────────────
            local_pip = os.path.join(_LOCAL_VENV_DIR, 'Scripts', 'pip.exe')
            if not os.path.isfile(local_pip):
                debug_log("venv-setup: pip not found at {}".format(local_pip))
                _setup_status['error'] = 'pip not found after venv creation'
                _setup_status['phase'] = 'error'
                return

            _setup_status['message'] = (
                u'Installing a few tools \u2014 this only happens once\u2026'
            )
            debug_log("venv-setup: installing {} ...".format(', '.join(_REQUIRED_PACKAGES)))

            # Try to add venv dir to Windows Defender exclusions so that
            # Defender doesn't lock .pyd files mid-install (WinError 5).
            # This is best-effort; failure is silently ignored.
            try:
                excl_cmd = [
                    'powershell', '-NonInteractive', '-WindowStyle', 'Hidden',
                    '-Command',
                    'Add-MpPreference -ExclusionPath "{}"'.format(_LOCAL_VENV_DIR)
                ]
                excl_proc = subprocess.Popen(
                    excl_cmd,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    shell=False, creationflags=0x08000000
                )
                # give it up to 10s; don't block the main flow
                _waited = 0
                while excl_proc.poll() is None and _waited < 10:
                    time.sleep(1)
                    _waited += 1
                if excl_proc.poll() is None:
                    excl_proc.kill()
                debug_log('venv-setup: Defender exclusion attempted (rc={})'.format(excl_proc.returncode))
            except Exception:
                pass  # non-critical

            t1 = time.time()
            _PIP_MAX_RETRIES = 5
            _PIP_RETRY_WAIT  = 15  # seconds between retries (lets Defender finish scanning)
            err_str = None
            for pip_attempt in range(_PIP_MAX_RETRIES + 1):
                if pip_attempt > 0:
                    msg = u'Still working, just a moment\u2026 (attempt {}/{})'.format(
                        pip_attempt, _PIP_MAX_RETRIES)
                    debug_log('venv-setup: ' + msg + ' ({}s)'.format(_PIP_RETRY_WAIT))
                    _setup_status['message'] = msg
                    _kill_daemon_if_running()
                    time.sleep(_PIP_RETRY_WAIT)
                result = subprocess.Popen(
                    # --ignore-installed: skip the uninstall step so pip doesn't
                    # choke on missing RECORD files from a prior partial install.
                    # --no-cache-dir: avoid stale wheels from earlier botched runs.
                    [local_pip, 'install', '--quiet',
                     '--ignore-installed', '--no-cache-dir'] + _REQUIRED_PACKAGES,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    shell=False, creationflags=0x08000000
                )
                _setup_proc = result
                while result.poll() is None:
                    _setup_status['message'] = (
                        u'Installing a few tools \u2014 this only happens once\u2026'
                        if pip_attempt == 0
                        else u'Still working, just a moment\u2026 (attempt {}/{})'.format(pip_attempt, _PIP_MAX_RETRIES)
                    )
                    time.sleep(2)
                out, err = result.communicate()
                _setup_proc = None
                if result.returncode != 0:
                    err_str = err.decode('utf-8', errors='replace') if isinstance(err, bytes) else str(err)
                    debug_log('venv-setup: pip attempt {}/{} FAILED: {}'.format(
                        pip_attempt + 1, _PIP_MAX_RETRIES + 1, err_str[:500]))
                    if 'WinError 5' not in err_str and 'Access is denied' not in err_str:
                        # Not an antivirus lock — don't retry, it won't help
                        break
                    continue  # retry

                # pip exited 0 — confirm packages actually import (Defender can
                # corrupt a .pyd mid-write without pip noticing)
                debug_log('venv-setup: pip rc=0, verifying imports...')
                _setup_status['message'] = u'Almost done, checking everything\u2026'
                if self._local_venv_is_valid():
                    err_str = None
                    break
                # imports failed — treat as WinError-5-style corruption and retry
                err_str = 'pip exit 0 but packages do not import (corrupted .pyd?)'
                debug_log('venv-setup: import verification FAILED on attempt {}/{}: {}'.format(
                    pip_attempt + 1, _PIP_MAX_RETRIES + 1, err_str))

            if err_str:
                if 'pip exit 0 but packages do not import' in err_str:
                    # pip succeeded but .pyd files blocked by Defender.
                    # Write sentinel so next load skips rebuild and re-checks.
                    debug_log(
                        'venv-setup: packages installed but imports blocked '
                        '(Defender?) -- writing sentinel, restart Revit to activate'
                    )
                    try:
                        open(_pip_sentinel, 'w').close()
                    except Exception:
                        pass
                    _setup_status['message'] = u'Almost ready \u2014 restart Revit to activate vector search'
                    _setup_status['phase'] = 'done'
                else:
                    _setup_status['error'] = err_str[:200]
                    _setup_status['phase'] = 'error'
                return

            elapsed = time.time() - t0
            debug_log(
                u"venv-setup: SUCCESS \u2014 packages verified and installed in {:.1f}s (total {:.1f}s). "
                u"Local venv will be used from next Revit session."
                .format(time.time() - t1, elapsed)
            )
            # Update our cached python path so any CLI fallback in *this* session
            # uses the freshly-built local venv, not the network .venv that was
            # selected before setup ran.
            self._python_path = _LOCAL_VENV_PYTHON
            debug_log('venv-setup: updated python path to local venv: {}'.format(_LOCAL_VENV_PYTHON))
            # Move to daemon_starting phase — the toast stays open showing
            # progress while the daemon warms up.  It only transitions to
            # 'done' once _get_or_start_daemon confirms the daemon is alive.
            _setup_status['phase']   = 'daemon_starting'
            _setup_status['message'] = u'Starting search engine\u2026'
            debug_log('venv-setup: starting daemon pre-warm now that venv is ready')
            self._prewarm_daemon()

        except Exception as e:
            debug_log("venv-setup: unexpected error: {}\n{}".format(
                e, __import__('traceback').format_exc()))
            _setup_status['error'] = str(e)[:200]
            _setup_status['phase'] = 'error'
        finally:
            _setup_proc = None
            try:
                os.remove(_LOCAL_VENV_LOCK)
            except Exception:
                pass

    # ------------------------------------------------------------------

    def _prewarm_daemon(self):
        """Kick off daemon startup in a background thread (fire-and-forget)."""
        def _run():
            port = self._get_or_start_daemon()
            # Mark setup fully complete once the daemon is confirmed ready.
            # If _setup_status is still in daemon_starting phase (i.e. this was
            # called from _create_local_venv), advance it to 'done' now so the
            # toast shows "Ready" and hybrid_search stops waiting.
            if _setup_status.get('phase') == 'daemon_starting':
                if port is not None:
                    _setup_status['message'] = u'Done!'
                    _setup_status['phase']   = 'done'
                else:
                    # Daemon failed to start — still mark done so the user
                    # isn't stuck waiting; CLI fallback will handle queries.
                    _setup_status['message'] = u'Ready (search engine could not start \u2014 will retry on first query)'
                    _setup_status['phase']   = 'done'
        try:
            import threading as _threading
            t = _threading.Thread(target=_run, name='kodama-daemon-prewarm')
            t.daemon = True
            t.start()
            debug_log("daemon: pre-warm thread started")
        except Exception as e:
            debug_log("daemon: pre-warm thread failed to start: {}".format(e))

    @staticmethod
    def _get_venv_base_python(python_exe):
        """
        If *python_exe* is the python.exe of a venv (i.e. a pyvenv.cfg exists at
        the venv root), return the base CPython 'executable' listed in that file.
        This allows bootstrap venv creation to work on machines other than the
        one that originally built the venv.  Returns None on any failure.
        """
        try:
            # Layout: <venv>/Scripts/python.exe  ->  venv root is two levels up
            venv_root = os.path.dirname(os.path.dirname(python_exe))
            pyvenv_cfg = os.path.join(venv_root, 'pyvenv.cfg')
            if not os.path.isfile(pyvenv_cfg):
                return None
            import io as _io
            with _io.open(pyvenv_cfg, 'r', encoding='utf-8', errors='replace') as _f:
                for line in _f:
                    key, sep, val = line.partition('=')
                    if sep and key.strip().lower() == 'executable':
                        exe = val.strip()
                        if exe and os.path.isfile(exe):
                            return exe
        except Exception:
            pass
        return None
    @staticmethod
    def _is_network_path(path):
        """Return True if *path* resides on a UNC share or a mapped network drive."""
        if not path:
            return False
        # UNC path (\\server\share\...)
        if path.startswith('\\\\') or path.startswith('//'):
            return True
        # Mapped drive: ask Windows whether the drive type is DRIVE_REMOTE (4)
        try:
            import ctypes
            drive = os.path.splitdrive(path)[0] + '\\'
            return ctypes.windll.kernel32.GetDriveTypeW(drive) == 4
        except Exception:
            pass
        return False

    def _find_bootstrap_python(self, start_dir):
        """
        Find the fastest available Python 3 for creating a new venv.
        Prefers locally-installed Python executables over network-drive paths.

        Resolution order:
          1. Windows 'py -3' launcher  (C:\\Windows\\py.exe — always local)
          2. python3.exe / python.exe on PATH that are NOT on a network drive
          3. Any python.exe found under LOCALAPPDATA\\Programs\\Python
          3b. pyRevit bundled CPython (%%APPDATA%%\\pyRevit-Master\\bin\\cengines\\CPY3*/)
              -- present on every pyRevit machine, no separate Python install
          4. Fall back to _find_python(skip_local_venv=True)  (may be network)
        """
        # 1. Windows py launcher — prefer 3.12 or 3.11 over 3.13.
        # Python 3.13 Rust-compiled .pyd wheels trigger Windows Defender
        # heuristics (WinError 5) because they are newer/less-trusted binaries.
        # 3.12 wheels are the same packages but with a different binary hash
        # that Defender accepts without quarantine.
        py_launcher = os.path.join(
            os.environ.get('WINDIR', 'C:\\Windows'), 'py.exe'
        )
        if os.path.isfile(py_launcher):
            for py_ver_flag in ('-3.12', '-3.11', '-3.10', '-3'):
                try:
                    r = subprocess.Popen(
                        [py_launcher, py_ver_flag, '--version'],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        shell=False, creationflags=0x08000000
                    )
                    r.communicate()
                    if r.returncode == 0:
                        debug_log('_find_bootstrap_python: using py launcher {} {}'.format(
                            py_launcher, py_ver_flag))
                        return [py_launcher, py_ver_flag]
                except Exception:
                    pass

        # 2. Local PATH pythons (skip network drives)
        try:
            import shutil as _shutil
            _which = getattr(_shutil, 'which', None)  # missing in IronPython 2.7
        except ImportError:
            _which = None
        if _which:
            for candidate_name in ('python3.exe', 'python.exe', 'python3', 'python'):
                candidate = _which(candidate_name)
                if candidate and os.path.isfile(candidate):
                    if not self._is_network_path(candidate):
                        debug_log('_find_bootstrap_python: using local PATH python: {}'.format(candidate))
                        return [candidate]

        # 3. Common LOCALAPPDATA install location (e.g. Microsoft Store Python)
        local_programs = os.path.join(
            os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python'
        )
        if os.path.isdir(local_programs):
            for entry in sorted(os.listdir(local_programs), reverse=True):
                exe = os.path.join(local_programs, entry, 'python.exe')
                if os.path.isfile(exe):
                    debug_log('_find_bootstrap_python: using LOCALAPPDATA python: {}'.format(exe))
                    return [exe]

        # 3b. pyRevit ships its own CPython engine -- present on every machine
        #     that runs pyRevit; no separate Python install required.
        #     Checks all known install locations (per-user and machine-wide).
        try:
            _appdata   = os.environ.get('APPDATA', '')
            _localapp  = os.environ.get('LOCALAPPDATA', '')
            _revit_engine_roots = [
                os.path.join(_appdata,  'pyRevit-Master', 'bin', 'cengines'),
                os.path.join(_appdata,  'pyRevit',        'bin', 'cengines'),
                os.path.join(_localapp, 'pyRevit-Master', 'bin', 'cengines'),
                os.path.join(_localapp, 'pyRevit',        'bin', 'cengines'),
                r'C:\ProgramData\pyRevit\bin\cengines',
            ]
            _preferred_order = ['CPY312', 'CPY311', 'CPY310', 'CPY313', 'CPY3']
            def _engine_priority(name):
                for idx, prefix in enumerate(_preferred_order):
                    if name.upper().startswith(prefix):
                        return idx
                return 99
            _found_3b = False
            for _revit_cengines in _revit_engine_roots:
                debug_log('_find_bootstrap_python: checking pyRevit cengines at {}'.format(_revit_cengines))
                if not os.path.isdir(_revit_cengines):
                    continue
                _all_engines = sorted(os.listdir(_revit_cengines), key=_engine_priority)
                for _eng in _all_engines:
                    if not _eng.upper().startswith('CPY3'):
                        continue
                    _exe = os.path.join(_revit_cengines, _eng, 'python.exe')
                    if os.path.isfile(_exe):
                        debug_log('_find_bootstrap_python: using pyRevit CPython engine: {}'.format(_exe))
                        _found_3b = True
                        return [_exe]
            if not _found_3b:
                debug_log('_find_bootstrap_python: pyRevit CPython engine not found in any location')
        except Exception as _e3b:
            debug_log('_find_bootstrap_python: step 3b error: {}'.format(_e3b))

        # 3c. Windows registry -- finds Python installed via the official installer
        #     even if not on PATH.  KEY_WOW64_32KEY is absent in IronPython's
        #     _winreg, so we only use the default (64-bit) view.
        try:
            try:
                import _winreg as _wr
            except ImportError:
                import winreg as _wr
            _preferred_order_reg = ['3.12', '3.11', '3.10', '3.13', '3.9']
            def _reg_priority(ver):
                for idx, v in enumerate(_preferred_order_reg):
                    if ver.startswith(v):
                        return idx
                return 99
            _reg_pythons = []
            for _hive in (_wr.HKEY_CURRENT_USER, _wr.HKEY_LOCAL_MACHINE):
                try:
                    _rk = _wr.OpenKey(_hive, r'SOFTWARE\Python\PythonCore', 0, _wr.KEY_READ)
                    _idx2 = 0
                    while True:
                        try:
                            _ver = _wr.EnumKey(_rk, _idx2)
                            _idx2 += 1
                            try:
                                _ik = _wr.OpenKey(_rk, _ver + r'\InstallPath')
                                _exe_path = _wr.QueryValueEx(_ik, 'ExecutablePath')[0]
                                if _exe_path and os.path.isfile(_exe_path) and not self._is_network_path(_exe_path):
                                    _reg_pythons.append((_reg_priority(_ver), _exe_path))
                            except Exception:
                                pass
                        except OSError:
                            break
                except Exception:
                    pass
            if _reg_pythons:
                _reg_pythons.sort(key=lambda x: x[0])
                _exe = _reg_pythons[0][1]
                debug_log('_find_bootstrap_python: using registry Python: {}'.format(_exe))
                return [_exe]
        except Exception as _ereg:
            debug_log('_find_bootstrap_python: registry search error: {}'.format(_ereg))

        # 3d. Disk scan of common Python install locations -- last resort before
        #     falling back to the network venv.  Covers machines where Python was
        #     installed without registering in the Windows registry or PATH.
        try:
            _disk_roots = [
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python'),
                r'C:\Python312', r'C:\Python311', r'C:\Python310', r'C:\Python313',
                r'C:\Program Files\Python312', r'C:\Program Files\Python311',
                r'C:\Program Files\Python310', r'C:\Program Files\Python313',
            ]
            _disk_preferred = ['312', '311', '310', '313', '39']
            def _disk_priority(path):
                for idx, v in enumerate(_disk_preferred):
                    if v in os.path.basename(os.path.dirname(path)):
                        return idx
                return 99
            _disk_hits = []
            for _droot in _disk_roots:
                if not os.path.isdir(_droot):
                    continue
                # Either the root is itself a Python dir (C:\Python312\python.exe)
                _direct = os.path.join(_droot, 'python.exe')
                if os.path.isfile(_direct) and not self._is_network_path(_direct):
                    _disk_hits.append(_direct)
                # Or it contains subdirectories (LOCALAPPDATA\Programs\Python\Python312\)
                try:
                    for _sub in os.listdir(_droot):
                        _candidate = os.path.join(_droot, _sub, 'python.exe')
                        if os.path.isfile(_candidate) and not self._is_network_path(_candidate):
                            _disk_hits.append(_candidate)
                except Exception:
                    pass
            if _disk_hits:
                _disk_hits.sort(key=_disk_priority)
                debug_log('_find_bootstrap_python: using disk-scan Python: {}'.format(_disk_hits[0]))
                return [_disk_hits[0]]
        except Exception as _edisk:
            debug_log('_find_bootstrap_python: disk scan error: {}'.format(_edisk))
        # 4. Fall back -- resolve via pyvenv.cfg or bare PATH python
        fallback = self._find_python(start_dir, skip_local_venv=True)
        base = self._get_venv_base_python(fallback)
        if base and os.path.isfile(base):
            debug_log(
                u'_find_bootstrap_python: resolved base interpreter from '
                u'pyvenv.cfg: {}'.format(base)
            )
            return [base]
        if base and not os.path.isfile(base):
            debug_log(
                u'_find_bootstrap_python: pyvenv.cfg base not found locally -- trying PATH'
            )
            for _lr in (['py.exe', '-3'], ['python3.exe'], ['python.exe'], ['python']):
                try:
                    _r = subprocess.Popen(_lr + ['--version'],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        shell=False, creationflags=0x08000000)
                    _r.communicate()
                    if _r.returncode == 0:
                        debug_log(u'_find_bootstrap_python: last-resort PATH Python: {}'.format(_lr[0]))
                        return _lr
                except Exception:
                    pass
            debug_log(
                u'_find_bootstrap_python: NO PYTHON FOUND on this machine. '
                u'Install Python 3.12 from python.org and restart Revit.'
            )
        debug_log(u'_find_bootstrap_python: WARNING - falling back to network python: {}'.format(fallback))
        return [fallback]

    def _find_python(self, start_dir, skip_local_venv=False):
        """
        Find the best available CPython 3 executable.  Resolution order:
          0. Local Kodama venv  (%LOCALAPPDATA%\\BBB\\Kodama\\venv)  – fastest
             (skipped when skip_local_venv=True, used for bootstrap venv creation)
          1. config vector_search.python_path  (explicit override)
          2. .venv relative to extension root  (dev/production venv)
          3. Windows 'py -3' launcher          (standard Python install)
          4. 'python3' / 'python'              (PATH fallback)

        Steps 1-2 are still tried even if the result is on a network drive, but
        a warning is logged so the performance impact is visible in the debug log.
        """
        # 0. Local Kodama venv – created by the user to avoid slow network imports
        if not skip_local_venv:
            local_venv = os.path.join(
                os.environ.get('LOCALAPPDATA', ''),
                'BBB', 'Kodama', 'venv', 'Scripts', 'python.exe'
            )
            if os.path.isfile(local_venv):
                debug_log("_find_python: using local Kodama venv: {}".format(local_venv))
                return local_venv

        # 1. Explicit config override
        configured = self.config.get_config('vector_search.python_path', None)
        if configured and os.path.isfile(configured):
            if self._is_network_path(configured):
                debug_log(
                    "_find_python: WARNING – configured python is on a network drive: {}. "
                    "Import time will be slow (~40-50 s). "
                    "Create a local venv at %LOCALAPPDATA%\\BBB\\Kodama\\venv to fix this."
                    .format(configured)
                )
            else:
                debug_log("_find_python: using config path: {}".format(configured))
            return configured

        # 2. Walk up from the script dir looking for a .venv
        search_dir = start_dir
        for _ in range(6):  # max 6 levels up
            candidate = os.path.join(search_dir, '.venv', 'Scripts', 'python.exe')
            if os.path.isfile(candidate):
                if self._is_network_path(candidate):
                    debug_log(
                        "_find_python: WARNING – discovered venv is on a network drive: {}. "
                        "Create a local venv at %LOCALAPPDATA%\\BBB\\Kodama\\venv to fix this."
                        .format(candidate)
                    )
                else:
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

    # ------------------------------------------------------------------
    # Daemon management
    # ------------------------------------------------------------------

    def _ping_daemon(self, port):
        """Return True if the daemon at *port* is responsive."""
        try:
            data = _http_get(port, '/ping', timeout=3)
            return data.get('ok', False)
        except Exception:
            return False

    def _get_or_start_daemon(self):
        """
        Return the port of a live daemon, starting one if necessary.
        Returns None if the daemon cannot be started.
        """
        # Fast path: we already know the port and it's still alive
        if self._daemon_port is not None:
            if self._ping_daemon(self._daemon_port):
                return self._daemon_port
            debug_log("daemon: cached port {} no longer responsive".format(self._daemon_port))
            self._daemon_port = None

        # Check state file for a daemon started by another code path
        pid, port = _read_daemon_state()
        if pid is not None and port is not None:
            if _is_pid_alive(pid) and self._ping_daemon(port):
                debug_log("daemon: reusing existing daemon PID={} port={}".format(pid, port))
                self._daemon_port = port
                return port
            else:
                debug_log("daemon: stale state file (PID={} port={}), will start new daemon".format(pid, port))

        # Start a new daemon process
        debug_log("daemon: starting new daemon process")
        try:
            CREATE_NO_WINDOW = 0x08000000
            # subprocess.DEVNULL was added in Python 3.3 and is absent in
            # IronPython 2.7 (the Revit host interpreter).  Open /dev/null
            # (os.devnull) explicitly so both runtimes work.
            _devnull = open(os.devnull, 'rb')
            proc = subprocess.Popen(
                [self.python_exe, self.daemon_script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=_devnull,
                shell=False,
                creationflags=CREATE_NO_WINDOW
            )
            _devnull.close()
        except Exception as e:
            debug_log("daemon: failed to launch process: {}".format(e))
            return None

        # Wait for DAEMON_READY line on stdout
        t0 = time.time()
        ready_port = None
        while time.time() - t0 < self.DAEMON_START_TIMEOUT:
            line = proc.stdout.readline()
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='replace')
            line = line.strip()
            if line.startswith('DAEMON_READY'):
                # Parse "DAEMON_READY port=NNNN"
                try:
                    ready_port = int(line.split('port=')[1])
                except Exception:
                    pass
                break
            if proc.poll() is not None:
                # Process exited prematurely
                stderr_out = proc.stderr.read()
                if isinstance(stderr_out, bytes):
                    stderr_out = stderr_out.decode('utf-8', errors='replace')
                debug_log("daemon: process exited early: {}".format(stderr_out[:500]))
                return None

        if ready_port is None:
            debug_log("daemon: timed out waiting for DAEMON_READY ({}s)".format(
                self.DAEMON_START_TIMEOUT))
            try:
                proc.kill()
            except Exception:
                pass
            return None

        debug_log("daemon: ready on port {} after {:.1f}s".format(
            ready_port, time.time() - t0))
        self._daemon_port = ready_port
        return ready_port

    # ------------------------------------------------------------------
    # Search – daemon-first, CLI fallback
    # ------------------------------------------------------------------

    def hybrid_search(self, query, n_results=10, deduplicate=True):
        """
        Execute hybrid search.  Tries daemon mode first; falls back to CLI.
        """
        debug_log("VectorDBInteropClient: hybrid_search for query: {}".format(
            safe_str(query)[:100]))

        # ── Wait for background venv/daemon setup if still in progress ────
        # On first launch, venv setup + daemon start can take ~90s.  If the
        # user fires a query before setup finishes, we wait here rather than
        # immediately falling back to the (potentially broken) network venv.
        _wait_phases = ('running', 'daemon_starting')
        if _setup_status.get('phase') in _wait_phases:
            debug_log('hybrid_search: setup phase={}, waiting up to 120s...'.format(
                _setup_status.get('phase')))
            _waited = 0
            while _setup_status.get('phase') in _wait_phases and _waited < 120:
                time.sleep(2)
                _waited += 2
            debug_log('hybrid_search: setup phase={} after {}s wait'.format(
                _setup_status.get('phase'), _waited))

        # ── Daemon path ──────────────────────────────────────────────────
        t0 = time.time()
        port = self._get_or_start_daemon()
        if port is not None:
            try:
                data = _http_post(
                    port, '/search',
                    {'query': query, 'n_results': n_results, 'deduplicate': deduplicate},
                    timeout=self.DAEMON_REQUEST_TIMEOUT
                )
                elapsed = time.time() - t0
                debug_log("TIMING daemon total={:.2f}s".format(elapsed))
                if data.get('success'):
                    results = data.get('results', [])
                    debug_log("VectorDBInteropClient: daemon returned {} results".format(len(results)))
                    return results
                else:
                    debug_log("daemon: search error: {}".format(
                        safe_str(data.get('error', ''))[:300]))
                    # Fall through to CLI
            except Exception as e:
                debug_log("daemon: HTTP request failed ({}), falling back to CLI".format(e))
                self._daemon_port = None  # force re-check next time

        # ── CLI fallback (original subprocess approach) ──────────────────
        debug_log("VectorDBInteropClient: using CLI fallback for query")
        return self._hybrid_search_cli(query, n_results, deduplicate)

    def _hybrid_search_cli(self, query, n_results=10, deduplicate=True):
        """Original one-shot subprocess implementation (fallback)."""
        try:
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
            t_subprocess_start = time.time()
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                shell=False,
                creationflags=CREATE_NO_WINDOW
            )
            
            stdout, stderr = process.communicate()
            t_subprocess_end = time.time()
            debug_log("TIMING subprocess total={:.2f}s returncode={}".format(
                t_subprocess_end - t_subprocess_start, process.returncode))
            
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


# ---------------------------------------------------------------------------
# Module-level helpers used by the Settings UI
# ---------------------------------------------------------------------------

def get_local_env_status():
    """Return a dict describing the current local venv state for the Settings UI."""
    exists = os.path.isfile(_LOCAL_VENV_PYTHON)
    phase  = _setup_status.get('phase', 'idle')
    msg    = _setup_status.get('message', u'')
    err    = _setup_status.get('error',   u'')

    if phase == 'running':
        state = u'Setting up… ' + (msg or u'')
    elif phase == 'daemon_starting':
        state = u'Starting search engine… ' + (msg or u'')
    elif phase == 'done':
        state = u'✓ Ready — local environment is installed'
    elif phase == 'error':
        state = u'⚠ Error: ' + (err or u'unknown')
    elif exists:
        state = u'✓ Ready — local environment is installed'
    else:
        state = u'○ Not installed — setup will run automatically on next launch'

    return {
        'path':   _LOCAL_VENV_DIR,
        'exists': exists,
        'phase':  phase,
        'state':  state,
    }


# ---------------------------------------------------------------------------
# Vector DB cache update helpers
# ---------------------------------------------------------------------------

# Shared status dict for background DB sync operations.
# Uses the same GIL-atomic dict pattern as _setup_status.
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
        # Same path resolution as VectorDBClient.__init__
        lib_dir     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir  = os.path.join(lib_dir, 'config')
        network_db_path  = os.path.join(config_dir, db_path_rel)
        network_sentinel = os.path.join(network_db_path, 'chroma.sqlite3')

        if not os.path.exists(network_sentinel):
            return False   # nothing on the network to sync

        local_db_path  = os.path.join(_STATE_DIR, 'vector_db')
        local_sentinel = os.path.join(local_db_path, 'chroma.sqlite3')

        if not os.path.exists(local_sentinel):
            return True   # no local copy at all

        return os.path.getmtime(network_sentinel) > os.path.getmtime(local_sentinel)

    except Exception as exc:
        debug_log('check_db_needs_update error: {}'.format(exc))
        return False


def start_db_sync_async(config_manager):
    """
    Start a background thread that copies the network vector DB to the local
    cache, then kills the search daemon so the next query picks up the new DB.
    Progress is written to the module-level ``_db_sync_status`` dict.
    """
    import threading as _threading
    import shutil    as _shutil

    try:
        db_path_rel      = config_manager.get_config('vector_search.db_path', 'vector_db')
        lib_dir          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir       = os.path.join(lib_dir, 'config')
        network_db_path  = os.path.join(config_dir, db_path_rel)
        local_db_path    = os.path.join(_STATE_DIR, 'vector_db')
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
            # Kill the daemon so it releases file handles on the old DB
            _kill_daemon_if_running()
            time.sleep(0.5)
            # Swap in the fresh DB
            if os.path.exists(local_db_path):
                _shutil.rmtree(local_db_path)
            _shutil.copytree(network_db_path, local_db_path)
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


def reset_local_env(rebuild=False):
    """
    Delete the local Kodama venv (and daemon state) so the next launch
    triggers a fresh setup.

    If rebuild=True, also kicks off an immediate background rebuild.
    Returns (success, message).
    """
    import shutil as _shutil
    deleted = False
    try:
        # Kill any in-progress setup subprocess first so it can't race with us
        global _setup_proc
        if _setup_proc is not None:
            try:
                _setup_proc.kill()
                debug_log('reset_local_env: killed in-progress setup process')
            except Exception as kill_err:
                debug_log('reset_local_env: could not kill setup process: {}'.format(kill_err))
            _setup_proc = None
        # Kill the daemon too — it may hold .pyd handles inside the venv
        _kill_daemon_if_running()
        time.sleep(1)  # give Windows a moment to release file handles
        if os.path.exists(_LOCAL_VENV_DIR):
            _shutil.rmtree(_LOCAL_VENV_DIR, ignore_errors=True)
            deleted = True
        # Remove stale daemon state so a new daemon is started next query
        if os.path.exists(_STATE_FILE):
            try:
                os.remove(_STATE_FILE)
            except Exception:
                pass
        # Remove stale lock so the next setup attempt isn't blocked
        if os.path.exists(_LOCAL_VENV_LOCK):
            try:
                os.remove(_LOCAL_VENV_LOCK)
            except Exception:
                pass
    except Exception as exc:
        return False, u'Error deleting local environment: {}'.format(exc)

    _setup_status['phase']      = 'idle'
    _setup_status['message']    = u''
    _setup_status['error']      = None
    _setup_status['start_time'] = None

    if rebuild:
        try:
            from standards_chat.config_manager import ConfigManager as _CM
            client = VectorDBInteropClient(_CM())
            client._ensure_local_venv_async()
        except Exception as exc:
            return True, u'Reset OK but could not start rebuild: {}'.format(exc)
        return True, u'Reset complete. Rebuilding in the background—you will see a progress toast.'

    if deleted:
        return True, (
            u'Local environment deleted. '
            u'Setup will run automatically next time you open Kodama.'
        )
    return True, u'Nothing to reset — local environment was not installed.'
