#! python3
"""
Clear Debug Log
Clears the debug log file
"""

import os

def clear_debug_log():
    """Clear the debug log file"""
    log_dir = os.path.join(os.environ.get('APPDATA', ''), 'BBB', 'StandardsAssistant')
    log_path = os.path.join(log_dir, 'debug_log.txt')
    
    if os.path.exists(log_path):
        os.remove(log_path)
        print(f"Debug log cleared: {log_path}")
    else:
        print(f"No debug log found at: {log_path}")

if __name__ == '__main__':
    clear_debug_log()
