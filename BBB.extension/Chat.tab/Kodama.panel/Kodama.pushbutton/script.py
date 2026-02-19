# -*- coding: utf-8 -*-
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
            # Show disclaimer window (modal)
            disclaimer = DisclaimerWindow()
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
        
        # Check if window is already open
        # Note: script.get_window may not work as expected with custom Window classes
        # For now, just create a new window each time
        
        # Create and show new window
        chat_window = StandardsChatWindow()
        chat_window.Show()
        
    except Exception as e:
        forms.alert(
            "Failed to open Standards Chat:\n{}".format(str(e)),
            title="Error",
            warn_icon=True
        )


if __name__ == '__main__':
    main()
