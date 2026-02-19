# -*- coding: utf-8 -*-
"""
Settings - Configuration Interface
Opens settings dialog for API keys and configuration
"""

from pyrevit import forms
import sys
import os

# Add lib path (3 levels up: Settings.pushbutton -> Kodama.panel -> Chat.tab -> BBB.extension)
_script_dir = os.path.dirname(__file__)
_lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_script_dir))), 'lib')
if _lib_path not in sys.path:
    sys.path.insert(0, _lib_path)

__title__ = "Settings"
__author__ = "BBB DCT Team"
__doc__ = "Configure API keys and settings for Standards Assistant"

def main():
    """Open settings dialog"""
    # Defer import to prevent pyRevit C# session creation errors at startup
    try:
        from standards_chat.settings_window import SettingsWindow
    except Exception as e:
        forms.alert(
            "Failed to load Settings modules:\n{}".format(str(e)),
            title="Import Error",
            warn_icon=True
        )
        return

    try:
        # Get config directory
        # Navigate from Settings.pushbutton/script.py up to BBB.extension/config
        config_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'config'
        )
        
        api_keys_path = os.path.join(config_dir, 'api_keys.json')
        config_path = os.path.join(config_dir, 'config.json')
        
        # Check if files exist
        if not os.path.exists(api_keys_path) or not os.path.exists(config_path):
            forms.alert(
                "Configuration files not found.\n\n"
                "Please ensure the extension is properly installed.",
                title="Configuration Error",
                warn_icon=True
            )
            return
        
        # Open settings window
        window = SettingsWindow(config_dir)
        window.ShowDialog()
        
    except Exception as e:
        forms.alert(
            "Error opening settings:\n{}".format(str(e)),
            title="Error",
            warn_icon=True
        )


if __name__ == '__main__':
    main()
