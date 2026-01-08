# -*- coding: utf-8 -*-
"""
Configuration Manager
Handles loading and accessing configuration
"""

import os
import json


class ConfigManager:
    """Manages configuration and API keys"""
    
    def __init__(self):
        """Initialize config manager"""
        # Get extension directory
        self.extension_dir = self._get_extension_dir()
        self.config_dir = os.path.join(self.extension_dir, 'config')
        
        # Load configuration files
        self.config = self._load_json('config.json')
        self.api_keys = self._load_json('api_keys.json')
    
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
        
        with open(filepath, 'r') as f:
            return json.load(f)
    
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
        """Save current configuration to config.json"""
        filepath = os.path.join(self.config_dir, 'config.json')
        with open(filepath, 'w') as f:
            json.dump(self.config, f, indent=2)
    
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
