# -*- coding: utf-8 -*-
import sys; sys.dont_write_bytecode = True  # never write .pyc to network share
"""
Standards Chat - Main Entry Point
Opens the chat interface for querying BBB Revit standards
"""

from pyrevit import script, forms
import sys
import os

# Add lib path to system path
_lib_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'lib'
)
if _lib_path not in sys.path:
    sys.path.insert(0, _lib_path)

__title__ = "Standards\nChat"
__author__ = "BBB DCT Team"
__doc__ = "AI-powered assistant for BBB Revit standards"


def main():
    """Launch the standards chat window"""
    # Defer heavy imports to here so pyRevit session creation doesn't fail
    try:
        from standards_chat.chat_window import StandardsChatWindow
        from standards_chat.disclaimer_window import DisclaimerWindow
        from standards_chat.config_manager import ConfigManager
    except Exception as e:
        forms.alert(
            "Failed to load Standards Chat modules:\n{}".format(str(e)),
            title="Import Error",
            warn_icon=True
        )
        return

    try:
        # Initialize config manager
        config_manager = ConfigManager()

        # ------------------------------------------------------------------
        # Helper: create and show the chat window.
        # Defined early so it can be passed as a callback to the setup toast.
        # ------------------------------------------------------------------
        def _launch_chat_window():
            chat_window = StandardsChatWindow()
            chat_window.Show()

        # Check if user has seen and accepted disclaimer
        # Use hasattr for backwards compatibility with cached modules
        if hasattr(config_manager, 'has_accepted_disclaimer'):
            has_accepted = config_manager.has_accepted_disclaimer()
        else:
            # Fallback for cached module - check directly
            has_accepted = config_manager.get('user', 'has_seen_disclaimer', False)

        # ------------------------------------------------------------------
        # Check whether numpy is available in pyRevit's CPython.
        # This is a fast filesystem check — no subprocess on normal installs.
        # Fail-safe: default to True so we never block launch on any error.
        # ------------------------------------------------------------------
        numpy_installed = True
        try:
            from standards_chat import vector_db_interop as _vdb
            numpy_installed = _vdb.check_numpy_installed()
        except Exception:
            pass

        if not has_accepted:
            # First launch: show full disclaimer; reveal install panel if needed
            disclaimer = DisclaimerWindow()
            disclaimer._setup_needed = not numpy_installed
            result = disclaimer.ShowDialog()

            # If user declined or closed window, exit
            if not result:
                return

            # User accepted - save acceptance
            if hasattr(config_manager, 'mark_disclaimer_accepted'):
                config_manager.mark_disclaimer_accepted()
            else:
                # Fallback for cached module - save directly
                from datetime import datetime
                if 'user' not in config_manager.config:
                    config_manager.config['user'] = {}
                config_manager.config['user']['has_seen_disclaimer'] = True
                config_manager.config['user']['disclaimer_accepted_date'] = datetime.now().isoformat()
                config_manager.config['user']['disclaimer_version'] = '1.0'
                config_manager.save()

            # If the user chose "Not right now" on the install panel, stop here.
            # Disclaimer is saved — they won't be prompted again.  The install
            # panel will be shown again the next time they open Kodama.
            if not getattr(disclaimer, 'wants_to_launch', True):
                return

        elif not numpy_installed:
            # Disclaimer was accepted on a prior launch but numpy is still
            # missing (user chose "Not right now" before).
            # Skip the disclaimer text and show only the install panel.
            disclaimer = DisclaimerWindow()
            disclaimer._setup_needed = True
            disclaimer.show_install_panel_only()
            result = disclaimer.ShowDialog()

            if not result:
                return

            # "Not right now" again — come back next session
            if not getattr(disclaimer, 'wants_to_launch', True):
                return

        # ------------------------------------------------------------------
        # If numpy needs installing (user just chose "Get Kodama Ready Now"),
        # start a background pip install and show the progress toast.
        # The toast's "Launch Now" button calls _launch_chat_window() when done.
        # ------------------------------------------------------------------
        if not numpy_installed:
            try:
                from standards_chat import vector_db_interop as _vdb
                from standards_chat.setup_progress_window import SetupProgressWindow
                _vdb.start_numpy_install_async()
                setup_toast = SetupProgressWindow(status_dict=_vdb._numpy_setup_status)
                setup_toast.set_launch_callback(_launch_chat_window)
                setup_toast.Show()
                return  # Kodama opens via "Launch Now" button when install finishes
            except Exception:
                pass  # fall through — pip guard in search_vector_db.py handles it

        # ------------------------------------------------------------------
        # Startup DB update check — if the network has a newer standards DB
        # show a friendly progress window while we sync, then open Kodama.
        # ------------------------------------------------------------------
        needs_db_update = False
        try:
            from standards_chat import vector_db_interop as _vdb
            needs_db_update = _vdb.check_db_needs_update(config_manager)
        except Exception:
            pass   # non-critical — fall through to normal launch

        if needs_db_update:
            try:
                from standards_chat import vector_db_interop as _vdb
                from standards_chat.db_update_window import DBUpdateWindow
                _vdb.start_db_sync_async(config_manager)
                # Show a small bottom-right toast — Kodama opens immediately
                # in the background while the sync runs.
                toast = DBUpdateWindow(
                    status_dict=_vdb._db_sync_status,
                    startup=False
                )
                toast.Show()
            except Exception:
                pass  # non-critical — Kodama still opens below

        # Always open Kodama immediately, regardless of whether a sync is running
        _launch_chat_window()
        
    except Exception as e:
        forms.alert(
            "Failed to open Standards Chat:\n{}".format(str(e)),
            title="Error",
            warn_icon=True
        )


if __name__ == '__main__':
    main()
