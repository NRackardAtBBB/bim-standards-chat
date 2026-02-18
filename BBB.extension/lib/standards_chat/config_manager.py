# -*- coding: utf-8 -*-
"""
Configuration Manager
Handles loading and accessing configuration
"""

import os
import io
import json


class ConfigManager:
    """Manages configuration and API keys"""
    
    def __init__(self):
        """Initialize config manager"""
        # Get extension directory
        self.extension_dir = self._get_extension_dir()
        self.config_dir = os.path.join(self.extension_dir, 'config')
        
        # User preferences path (LocalLow)
        self.user_data_dir = os.path.join(os.path.expanduser('~'), 'AppData', 'LocalLow', 'BBB', 'Kodama')
        self.user_prefs_path = os.path.join(self.user_data_dir, 'user_preferences.json')

        # Load configuration files
        self.config = self._load_json('config.json')
        self.api_keys = self._load_json('api_keys.json')

        # Load and merge user preferences
        self._load_and_merge_user_prefs()

    def _load_and_merge_user_prefs(self):
        """Load user preferences from AppData and merge into config"""
        user_prefs = {}
        if os.path.exists(self.user_prefs_path):
            f = None
            try:
                f = io.open(self.user_prefs_path, 'r', encoding='utf-8')
                user_prefs = json.load(f)
            except Exception:
                pass
            finally:
                if f:
                    try:
                        f.close()
                    except:
                        pass
        
        self.config['user'] = user_prefs

    def _save_user_prefs(self, user_prefs):
        """Save user preferences to AppData"""
        # Create directory only when actually saving
        if not os.path.exists(self.user_data_dir):
            try:
                os.makedirs(self.user_data_dir)
            except OSError:
                pass
        
        f = None
        try:
            f = io.open(self.user_prefs_path, 'w', encoding='utf-8')
            json_str = json.dumps(user_prefs, indent=2, ensure_ascii=False)
            f.write(unicode(json_str))
        except Exception:
            pass
        finally:
            if f:
                try:
                    f.close()
                except:
                    pass

    def _get_extension_dir(self):
        """Get the extension directory path"""
        # Navigate up from lib/standards_chat to extension root
        current_file = __file__
        lib_dir = os.path.dirname(os.path.dirname(current_file))
        extension_dir = os.path.dirname(lib_dir)
        return extension_dir
    
    def _load_json(self, filename):
        """Load JSON file from config directory"""
        filepath = os.path.join(self.config_dir, filename)
        
        if not os.path.exists(filepath):
            raise Exception(
                "Configuration file not found: {}".format(filepath)
            )
        
        f = None
        try:
            f = io.open(filepath, 'r', encoding='utf-8')
            return json.load(f)
        finally:
            if f:
                try:
                    f.close()
                except:
                    pass
    
    def get(self, section, key, default=None):
        """Get configuration value"""
        try:
            return self.config[section][key]
        except KeyError:
            return default
    
    def get_config(self, key_path, default=None):
        """
        Get configuration value using dot notation for nested keys.
        
        Args:
            key_path: Dot-separated path to config value (e.g. 'vector_search.chunk_size')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_config(self, key_path, value):
        """
        Set configuration value using dot notation for nested keys.
        
        Args:
            key_path: Dot-separated path to config value (e.g. 'vector_search.last_sync_timestamp')
            value: Value to set
        """
        keys = key_path.split('.')
        config = self.config
        
        # Navigate to parent
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # Set value
        config[keys[-1]] = value
    
    def save(self):
        """
        Save current configuration.
        Splits 'user' settings to AppData and the rest to config.json.
        """
        # 1. Save User Prefs
        if 'user' in self.config:
            self._save_user_prefs(self.config['user'])

        # 2. Save Central Config
        # Create a copy without the user section to avoid writing it back to central
        config_to_save = self.config.copy()
        if 'user' in config_to_save:
            del config_to_save['user']

        filepath = os.path.join(self.config_dir, 'config.json')
        f = None
        try:
            f = open(filepath, 'w')
            json.dump(config_to_save, f, indent=2)
        finally:
            if f:
                try:
                    f.close()
                except:
                    pass

    def save_api_keys(self):
        """Save API keys to api_keys.json"""
        filepath = os.path.join(self.config_dir, 'api_keys.json')
        f = None
        try:
            f = open(filepath, 'w')
            json.dump(self.api_keys, f, indent=2)
        finally:
            if f:
                try:
                    f.close()
                except:
                    pass

    def get_api_key(self, service):
        """Get API key for a service"""
        key_name = "{}_api_key".format(service)
        
        if key_name not in self.api_keys:
            raise Exception(
                "API key for '{}' not found in api_keys.json".format(service)
            )
        
        api_key = self.api_keys[key_name]
        
        if not api_key or api_key.startswith('your-') or api_key.startswith('sk-ant-xxx'):
            raise Exception(
                "Please configure valid API key for '{}' in api_keys.json".format(service)
            )
        
        return api_key

    def get_secret(self, key_name):
        """Get a specific secret from api_keys.json"""
        if key_name not in self.api_keys:
            raise Exception(
                "Secret '{}' not found in api_keys.json".format(key_name)
            )
        return self.api_keys[key_name]

    def has_accepted_disclaimer(self):
        """Check if user has accepted the disclaimer"""
        return self.get('user', 'has_seen_disclaimer', False)
    
    def mark_disclaimer_accepted(self):
        """Mark disclaimer as accepted and save to user preferences"""
        from datetime import datetime
        
        if 'user' not in self.config:
            self.config['user'] = {}
        
        self.config['user']['has_seen_disclaimer'] = True
        self.config['user']['disclaimer_accepted_date'] = datetime.now().isoformat()
        self.config['user']['disclaimer_version'] = '1.0'
        
        self.save()
