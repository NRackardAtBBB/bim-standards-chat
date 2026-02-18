# -*- coding: utf-8 -*-
"""
History Manager
Manages chat session history storage and retrieval
"""

import json
import io
import os
from datetime import datetime


def _safe_print(message):
    """Print message safely, handling Unicode errors"""
    try:
        print(message)
    except UnicodeEncodeError:
        try:
            print(message.encode('ascii', 'replace').decode('ascii'))
        except:
            pass


class HistoryManager:
    """Manages chat history persistence in user's AppData"""
    
    def __init__(self):
        """Initialize history manager"""
        # Set up history directory in AppData
        appdata = os.environ.get('APPDATA', '')
        if appdata:
            self.history_dir = os.path.join(
                appdata,
                'BBB',
                'StandardsAssistant',
                'History'
            )
        else:
            # Fallback to temp
            self.history_dir = os.path.join(
                os.environ.get('TEMP', ''),
                'BBB_StandardsAssistant_History'
            )
        
        # Create directory if it doesn't exist
        if not os.path.exists(self.history_dir):
            try:
                os.makedirs(self.history_dir)
            except Exception as e:
                _safe_print("Error creating history directory: {}".format(str(e)))
    
    def create_new_session(self):
        """
        Create a new session ID
        
        Returns:
            str: New session ID based on timestamp
        """
        return datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    
    def save_session(self, session_id, conversation, title=None):
        """
        Save a chat session to disk
        
        Args:
            session_id (str): Unique session identifier
            conversation (list): List of conversation exchanges
            title (str): Optional custom title, defaults to first user query
        """
        if not conversation:
            return
        
        # Generate title from first user query if not provided
        if not title:
            title = conversation[0].get('user', 'Untitled Chat')[:100]
        
        session_data = {
            'session_id': session_id,
            'title': title,
            'timestamp': datetime.now().isoformat(),
            'conversation': conversation
        }
        
        filepath = os.path.join(self.history_dir, '{}.json'.format(session_id))
        
        try:
            with io.open(filepath, 'w', encoding='utf-8') as f:
                # Use ensure_ascii=False to properly write Unicode characters
                f.write(json.dumps(session_data, indent=2, ensure_ascii=False))
        except Exception as e:
            _safe_print("Error saving session: {}".format(str(e)))
    
    def load_session(self, session_id):
        """
        Load a chat session from disk
        
        Args:
            session_id (str): Session identifier to load
            
        Returns:
            dict: Session data including conversation, or None if not found
        """
        filepath = os.path.join(self.history_dir, '{}.json'.format(session_id))
        
        if not os.path.exists(filepath):
            return None
        
        try:
            with io.open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            _safe_print("Error loading session: {}".format(str(e)))
            return None
    
    def list_sessions(self):
        """
        List all available chat sessions, sorted by date (newest first)
        
        Returns:
            list: List of dicts with session_id, title, timestamp
        """
        sessions = []
        
        if not os.path.exists(self.history_dir):
            return sessions
        
        try:
            for filename in os.listdir(self.history_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.history_dir, filename)
                    try:
                        with io.open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            sessions.append({
                                'session_id': data.get('session_id', filename[:-5]),
                                'title': data.get('title', 'Untitled Chat'),
                                'timestamp': data.get('timestamp', '')
                            })
                    except:
                        # Skip corrupted files
                        continue
        except Exception as e:
            _safe_print("Error listing sessions: {}".format(str(e)))
        
        # Sort by timestamp, newest first
        sessions.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return sessions
    
    def delete_session(self, session_id):
        """
        Delete a chat session from disk
        
        Args:
            session_id (str): Session identifier to delete
            
        Returns:
            bool: True if deleted successfully
        """
        filepath = os.path.join(self.history_dir, '{}.json'.format(session_id))
        
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                return True
            except Exception as e:
                _safe_print("Error deleting session: {}".format(str(e)))
                return False
        
        return False
    
    def get_history_dir(self):
        """Get the history directory path"""
        return self.history_dir

    def clear_all_sessions(self):
        """
        Delete all chat sessions from disk
        
        Returns:
            int: Number of sessions deleted
        """
        count = 0
        if not os.path.exists(self.history_dir):
            return 0
            
        try:
            for filename in os.listdir(self.history_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.history_dir, filename)
                    try:
                        os.remove(filepath)
                        count += 1
                    except:
                        continue
        except Exception as e:
            _safe_print("Error clearing history: {}".format(str(e)))
            
        return count
