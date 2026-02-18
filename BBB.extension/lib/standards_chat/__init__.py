# -*- coding: utf-8 -*-
"""
Standards Chat Library
Core modules for Kodama
"""

__version__ = "1.0.0"
__author__ = "BBB DCT Team"

# Export main classes
# These imports require IronPython/CLR, so wrap in try-except for CPython compatibility
__all__ = ['ConfigManager']

try:
    from standards_chat.chat_window import StandardsChatWindow
    from standards_chat.disclaimer_window import DisclaimerWindow
    from standards_chat.settings_window import SettingsWindow
    __all__.extend(['StandardsChatWindow', 'DisclaimerWindow', 'SettingsWindow'])
except ImportError:
    # Running in CPython without CLR - only ConfigManager available
    pass

from standards_chat.config_manager import ConfigManager

