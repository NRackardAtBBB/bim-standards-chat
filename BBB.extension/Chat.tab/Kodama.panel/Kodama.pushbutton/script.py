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
        
        # Check if user has seen and accepted disclaimer
        # Use hasattr for backwards compatibility with cached modules
        if hasattr(config_manager, 'has_accepted_disclaimer'):
            has_accepted = config_manager.has_accepted_disclaimer()
        else:
            # Fallback for cached module - check directly
            has_accepted = config_manager.get('user', 'has_seen_disclaimer', False)
        
        if not has_accepted:
            # Check cheaply whether the local venv needs to be created so the
            # disclaimer window can show the install-prompt panel only when needed.
            try:
                from standards_chat.vector_db_interop import _LOCAL_VENV_PYTHON
                _setup_needed = not os.path.isfile(_LOCAL_VENV_PYTHON)
            except Exception:
                _setup_needed = False

            # Show disclaimer window (modal)
            disclaimer = DisclaimerWindow()
            disclaimer._setup_needed = _setup_needed
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
            # Disclaimer is saved — they won't be prompted again.  Setup will
            # start automatically the next time they open Kodama.
            if not getattr(disclaimer, 'wants_to_launch', True):
                return
        
        # ------------------------------------------------------------------
        # Helper: create and show the chat window, deferring if venv setup
        # is still running (same logic as before, now in its own function
        # so it can be called as a callback from DBUpdateWindow).
        # ------------------------------------------------------------------
        def _launch_chat_window():
            chat_window = StandardsChatWindow()
            setup_deferred = False
            try:
                from standards_chat import vector_db_interop as _vdb_inner
                if _vdb_inner._setup_status.get('phase') == 'running':
                    toast = getattr(
                        getattr(chat_window, 'vector_db_client', None),
                        '_setup_toast', None
                    )
                    if toast is not None:
                        toast.set_launch_callback(chat_window.Show)
                        setup_deferred = True
            except Exception:
                pass
            if not setup_deferred:
                chat_window.Show()

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
