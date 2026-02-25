"""
Sync SharePoint content to vector database for semantic search.
Run this script manually or via scheduled task to update the search index.

Usage:
    python sync_sharepoint.py
"""
import sys
import os
import re
import importlib.util

try:
    from tqdm import tqdm as _tqdm
    _TQDM_AVAILABLE = True
except ImportError:
    _TQDM_AVAILABLE = False


class _ProgressTracker:
    """Maintains tqdm progress bars across repeated progress_callback calls."""

    def __init__(self):
        self._bar = None
        self._bar_label = None

    def __call__(self, message, current, total):
        match = re.match(r'Processed (\d+)/(\d+) (.+)', message)
        if match and _TQDM_AVAILABLE:
            done = int(match.group(1))
            total_items = int(match.group(2))
            label = match.group(3).strip()

            # Open a fresh bar whenever the label (phase) changes
            if self._bar is None or self._bar_label != label:
                if self._bar is not None:
                    self._bar.close()
                self._bar = _tqdm(
                    total=total_items,
                    desc=label.capitalize(),
                    unit=label.split()[-1],
                    leave=True,
                    file=sys.stdout,
                    dynamic_ncols=True,
                )
                self._bar_label = label

            self._bar.n = done
            self._bar.refresh()

            if done >= total_items:
                self._bar.close()
                self._bar = None
                self._bar_label = None
        else:
            # Phase-change message (no count) — close any open bar first
            self._close()
            if _TQDM_AVAILABLE:
                _tqdm.write(message)
            else:
                print("PROGRESS: {}".format(message))

    def _close(self):
        if self._bar is not None:
            self._bar.close()
            self._bar = None
            self._bar_label = None

# Add extension lib path — script lives in dev/, so BBB.extension is one level up
script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.join(script_dir, '..')
lib_path = os.path.join(repo_root, 'BBB.extension', 'lib')
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
    tracker = _ProgressTracker()
    sync_module.main(progress_callback=tracker)
