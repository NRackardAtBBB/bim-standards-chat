# -*- coding: utf-8 -*-
"""
History Manager
Manages chat session history storage and retrieval
"""

import json
import os
from datetime import datetime
from standards_chat.utils import safe_print, safe_str


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
                safe_print("Error creating history directory: {}".format(safe_str(e)))
    
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
        
        f = None
        try:
            import io
            # Use io.open for consistent unicode handling in Python 2 (IronPython)
            f = io.open(filepath, 'w', encoding='utf-8')
            # ensure_ascii=True forces ascii, which is safest for avoiding codec errors
            json_str = json.dumps(session_data, indent=2, ensure_ascii=True)
            f.write(unicode(json_str)) # Write the ascii-escaped unicode string
        except Exception as e:
            # Fallback
            if f:
                try:
                    f.close()
                except:
                    pass
                f = None
            try:
                f = open(filepath, 'w')
                json.dump(session_data, f, indent=2, ensure_ascii=True)
            except:
                safe_print("Error saving session: {}".format(safe_str(e)))
        finally:
            if f:
                try:
                    f.close()
                except:
                    pass
    
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
        
        f = None
        try:
            # First try reading as utf-8 using io
            import io
            f = io.open(filepath, 'r', encoding='utf-8')
            content = f.read()
            return json.loads(content)
        except Exception as e:
            if f:
                try:
                    f.close()
                except:
                    pass
                f = None
            try:
                # Fallback to default open (for older files or system encoding)
                f = open(filepath, 'r')
                result = json.load(f)
                return result
            except Exception as ex:
                safe_print("Error loading session: {}".format(safe_str(ex)))
                return None
        finally:
            if f:
                try:
                    f.close()
                except:
                    pass
    
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
                    f = None
                    try:
                        f = open(filepath, 'r')
                        data = json.load(f)
                        sessions.append({
                            'session_id': data.get('session_id', filename[:-5]),
                            'title': data.get('title', 'Untitled Chat'),
                            'timestamp': data.get('timestamp', '')
                        })
                    except:
                        # Skip corrupted files
                        continue
                    finally:
                        if f:
                            try:
                                f.close()
                            except:
                                pass
        except Exception as e:
            safe_print("Error listing sessions: {}".format(safe_str(e)))
        
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
                safe_print("Error deleting session: {}".format(safe_str(e)))
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
            safe_print("Error clearing history: {}".format(safe_str(e)))
            
        return count
