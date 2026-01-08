# -*- coding: utf-8 -*-
"""
Standards Chat - Main Entry Point
Opens the chat interface for querying BBB Revit standards
"""

from pyrevit import script, forms
import sys
import os

# Add lib path to system path
lib_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'lib'
)
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

from standards_chat.chat_window import StandardsChatWindow

__title__ = "Standards\nChat"
__author__ = "BBB DCT Team"
__doc__ = "AI-powered assistant for BBB Revit standards"


def main():
    """Launch the standards chat window"""
    try:
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
