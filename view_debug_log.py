#! python3
"""
View Debug Log
Displays the last 50 lines of the debug log file
"""

import os
from datetime import datetime

def view_debug_log():
    """View the debug log file"""
    log_dir = os.path.join(os.environ.get('APPDATA', ''), 'BBB', 'StandardsAssistant')
    log_path = os.path.join(log_dir, 'debug_log.txt')
    
    if not os.path.exists(log_path):
        print(f"No debug log found at: {log_path}")
        return
    
    print("=" * 80)
    print(f"Debug Log: {log_path}")
    print("=" * 80)
    
    # Read last 50 lines
    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    print(f"\nTotal log entries: {len(lines)}")
    print("\nShowing last 50 lines:\n")
    print("-" * 80)
    
    for line in lines[-50:]:
        print(line.rstrip())
    
    print("-" * 80)
    print(f"\nFull log available at: {log_path}")

if __name__ == '__main__':
    view_debug_log()
