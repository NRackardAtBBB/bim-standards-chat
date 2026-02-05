# -*- coding: utf-8 -*-
"""
Usage Logger
Tracks usage analytics for Standards Chat
"""

import json
import os
import time
import base64
from datetime import datetime, timedelta
import hashlib
from standards_chat.utils import safe_print, safe_str


class UsageLogger:
    """Log chat interactions for analytics"""
    
    def __init__(self, local_log_dir=None, central_log_dir=None):
        """
        Initialize usage logger
        
        Args:
            local_log_dir: Local directory for detailed logs (user's machine)
            central_log_dir: Network directory for aggregated analytics (optional)
        """
        # Local logs (detailed, on user machine)
        if local_log_dir:
            self.local_log_dir = local_log_dir
        else:
            # Default to user's AppData
            appdata = os.environ.get('APPDATA', '')
            if appdata:
                self.local_log_dir = os.path.join(
                    appdata,
                    'BBB',
                    'StandardsChat',
                    'logs'
                )
            else:
                # Fallback to temp
                self.local_log_dir = os.path.join(
                    os.environ.get('TEMP', ''),
                    'BBB_StandardsChat_logs'
                )
        
        # Create local log directory
        if not os.path.exists(self.local_log_dir):
            try:
                os.makedirs(self.local_log_dir)
            except:
                pass
        
        # Central analytics (aggregated, on network share)
        self.central_log_dir = central_log_dir
        
        # Local log file (one per day)
        today = datetime.now().strftime('%Y-%m-%d')
        self.local_log_file = os.path.join(
            self.local_log_dir,
            'chat_log_{}.jsonl'.format(today)
        )
        
        # Get anonymous user ID (hash of username + machine name)
        self.user_id = self._get_anonymous_user_id()
    
    def log_interaction(self, query, response_preview, source_count, 
                       duration_seconds, revit_context=None, session_id=None, screenshot_base64=None, source_urls=None,
                       input_tokens=0, output_tokens=0, ai_model=None):
        """
        Log a chat interaction
        
        Args:
            query: User's question
            response_preview: Response text
            source_count: Number of sources found
            duration_seconds: Time taken to respond
            revit_context: Dict of Revit context (optional)
            session_id: Unique session identifier
            screenshot_base64: Base64 encoded screenshot string
            source_urls: List of source URLs
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            ai_model: Claude model used (e.g., 'claude-3-5-sonnet-20241022')
        """
        timestamp = datetime.utcnow().isoformat()
        
        # Local detailed log entry
        local_entry = {
            'timestamp': timestamp,
            'user_id': self.user_id,
            'session_id': session_id,
            'query': query,
            'query_length': len(query),
            'response_preview': response_preview[:100] if response_preview else '',
            'source_count': source_count,
            'source_urls': source_urls or [],
            'duration_seconds': round(duration_seconds, 2),
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
            'ai_model': ai_model,
            'has_revit_context': revit_context is not None
        }
        
        # Add Revit context summary
        if revit_context:
            local_entry['revit_context_summary'] = {
                'has_selection': 'selection' in revit_context if isinstance(revit_context, dict) else False,
                'has_screenshot': screenshot_base64 is not None,
                'view_type': revit_context.get('view', {}).get('view_type') if isinstance(revit_context, dict) else None,
                'is_workshared': revit_context.get('document', {}).get('is_workshared') if isinstance(revit_context, dict) else None
            }
        
        self._write_local_log(local_entry)
        
        # Central aggregated analytics entry
        if self.central_log_dir:
            # Handle screenshot
            screenshot_path = None
            if screenshot_base64:
                screenshot_path = self._save_screenshot(screenshot_base64, session_id, timestamp)

            # Get raw username from context if available, else use env var
            username = os.environ.get('USERNAME', 'unknown')
            if revit_context and 'username' in revit_context:
                username = revit_context['username']

            central_entry = {
                'timestamp': timestamp,
                'username': username,
                'session_id': session_id,
                'query': query,
                'response': response_preview, # Full response requested
                'source_count': source_count,
                'source_urls': source_urls or [],
                'duration_seconds': round(duration_seconds, 2),
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': input_tokens + output_tokens,
                'ai_model': ai_model,
                'model_name': revit_context.get('project_name') if revit_context else None,
                'view_name': revit_context.get('active_view') if revit_context else None,
                'selection_count': revit_context.get('selection_count', 0) if revit_context else 0,
                'has_screenshot': screenshot_base64 is not None,
                'screenshot_path': screenshot_path
            }
            
            self._write_central_log(central_entry, username, session_id)
    
    def _write_local_log(self, entry):
        """Write entry to local log file"""
        try:
            # Force utf-8 encoding for file open
            import io
            with io.open(self.local_log_file, 'a', encoding='utf-8') as f:
                # Ensure json dump produces ascii-safe string
                json_str = json.dumps(entry, ensure_ascii=True)
                f.write(unicode(json_str) + u'\n')
        except Exception as e:
            # Fallback for severe encoding issues
            try:
                with open(self.local_log_file, 'a') as f:
                    # Fallback to ascii-escaped json
                    f.write(json.dumps(entry, ensure_ascii=True) + '\n')
            except Exception:
                pass # Give up silencing error to avoid crashing app
    
    def _write_central_log(self, entry, username, session_id):
        """Write entry to central network location (session specific file)"""
        if not self.central_log_dir:
            return
        
        try:
            # Ensure central directory exists
            if not os.path.exists(self.central_log_dir):
                try:
                    os.makedirs(self.central_log_dir)
                except:
                    pass
            
            # Ensure session_id is usable (fallback to timestamp if None)
            if not session_id:
                session_id = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

            # Create session filename: YYYY-MM-DD_Username_SessionID.json
            date_str = datetime.now().strftime('%Y-%m-%d')
            safe_username = "".join([c for c in username if c.isalnum() or c in (' ', '.', '_')]).strip()
            filename = "{}_{}_{}.json".format(date_str, safe_username, session_id)
            file_path = os.path.join(self.central_log_dir, filename)
            
            # Append to session file (list of objects)
            # Using JSONL is safer for appending and PowerBI supports it
            import io
            with io.open(file_path, 'a', encoding='utf-8') as f:
                json_str = json.dumps(entry, ensure_ascii=True)
                f.write(unicode(json_str) + u'\n')
                
        except Exception as e:
            # Fallback
            try:
                # Use standard open with ascii escaping
                file_path = os.path.join(self.central_log_dir, filename)
                with open(file_path, 'a') as f:
                     f.write(json.dumps(entry, ensure_ascii=True) + '\n')
            except:
                safe_print("Could not write to central log: {}".format(safe_str(e)))

    def _save_screenshot(self, base64_str, session_id, timestamp):
        """Save screenshot to central directory"""
        if not self.central_log_dir:
            return None
            
        try:
            screenshots_dir = os.path.join(self.central_log_dir, 'screenshots')
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir)
                
            # Create filename
            ts_safe = timestamp.replace(':', '-').replace('.', '-')
            filename = "{}_{}.png".format(session_id, ts_safe)
            file_path = os.path.join(screenshots_dir, filename)
            
            # Decode and save
            with open(file_path, "wb") as fh:
                fh.write(base64.b64decode(base64_str))
                
            return file_path
        except Exception as e:
            safe_print("Error saving screenshot: {}".format(safe_str(e)))
            return None
    
    def _get_anonymous_user_id(self):
        """Generate anonymous user ID from username + machine"""
        try:
            import socket
            username = os.environ.get('USERNAME', 'unknown')
            machine = socket.gethostname()
            combined = "{}@{}".format(username, machine)
            
            # Create hash for anonymity
            hash_obj = hashlib.md5(combined.encode('utf-8'))
            return hash_obj.hexdigest()[:12]  # First 12 chars
        except:
            return 'unknown'
    
    def _extract_keywords(self, query):
        """
        Extract key terms from query for analytics (privacy-conscious)
        Returns common Revit/BIM terms, not user-specific content
        """
        keywords = []
        
        # Common terms to track
        common_terms = [
            'workset', 'view', 'template', 'family', 'level', 'phase',
            'link', 'sheet', 'schedule', 'filter', 'parameter', 'type',
            'wall', 'door', 'window', 'room', 'area', 'detail',
            'guardian', 'warning', 'error', 'standard', 'guideline',
            'naming', 'organization', 'setup', 'create', 'delete',
            'modify', 'copy', 'move', 'annotation', 'dimension',
            'tag', 'legend', 'section', 'elevation', 'plan',
            'line', 'style', 'weight', 'pattern', 'color'
        ]
        
        query_lower = query.lower()
        
        for term in common_terms:
            if term in query_lower:
                keywords.append(term)
        
        return keywords[:5]  # Max 5 keywords
    
    def get_usage_stats(self, days=30):
        """
        Get usage statistics from local logs
        
        Args:
            days: Number of days to analyze
            
        Returns:
            dict: Usage statistics
        """
        stats = {
            'total_queries': 0,
            'avg_duration': 0,
            'avg_sources': 0,
            'queries_per_day': {},
            'peak_hours': {}
        }
        
        try:
            durations = []
            sources = []
            hours_count = {}
            
            # Read all log files from last N days
            for i in range(days):
                date = datetime.now() - timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                log_file = os.path.join(
                    self.local_log_dir,
                    'chat_log_{}.jsonl'.format(date_str)
                )
                
                if not os.path.exists(log_file):
                    continue
                
                day_count = 0
                
                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            stats['total_queries'] += 1
                            day_count += 1
                            
                            durations.append(entry.get('duration_seconds', 0))
                            sources.append(entry.get('source_count', 0))
                            
                            # Track hour
                            timestamp = entry.get('timestamp', '')
                            if timestamp:
                                try:
                                    dt = datetime.strptime(timestamp.split('.')[0], '%Y-%m-%dT%H:%M:%S')
                                    hour = dt.hour
                                    hours_count[hour] = hours_count.get(hour, 0) + 1
                                except:
                                    pass
                            
                        except:
                            continue
                
                stats['queries_per_day'][date_str] = day_count
            
            # Calculate averages
            if durations:
                stats['avg_duration'] = sum(durations) / len(durations)
            if sources:
                stats['avg_sources'] = sum(sources) / len(sources)
            
            # Peak hours
            stats['peak_hours'] = dict(
                sorted(hours_count.items(), key=lambda x: x[1], reverse=True)[:5]
            )
            
        except Exception as e:
            safe_print("Error calculating stats: {}".format(safe_str(e)))
        
        return stats
