# -*- coding: utf-8 -*-
"""
Settings - Configuration Interface
Opens settings dialog for API keys and configuration
"""

from pyrevit import forms
import sys
import os
import json
import System

__title__ = "Settings"
__author__ = "BBB DCT Team"
__doc__ = "Configure API keys and settings for Standards Assistant"


class SettingsWindow(forms.WPFWindow):
    """Settings configuration window"""
    
    def __init__(self, config_dir):
        """Initialize settings window"""
        self.config_dir = config_dir
        self.api_keys_path = os.path.join(config_dir, 'api_keys.json')
        self.config_path = os.path.join(config_dir, 'config.json')
        
        # Load current settings
        self.load_settings()
        
        # Create XAML path in ui folder
        # Navigate from Settings.pushbutton/script.py up to BBB.extension
        extension_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        xaml_path = os.path.join(extension_dir, 'lib', 'ui', 'settings_window.xaml')
        
        forms.WPFWindow.__init__(self, xaml_path)
        
        # Populate fields with current values
        self.populate_fields()
    
    def load_settings(self):
        """Load current settings from JSON files"""
        try:
            with open(self.api_keys_path, 'r') as f:
                self.api_keys = json.load(f)
            
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        except Exception as e:
            forms.alert(
                "Error loading settings:\n{}".format(str(e)),
                title="Error",
                warn_icon=True
            )
            self.api_keys = {}
            self.config = {}
    
    def populate_fields(self):
        """Populate UI fields with current values"""
        # General Settings
        self.user_name.Text = self.config.get('user', {}).get('name', '')
        self.user_team.Text = self.config.get('user', {}).get('team', '')
        self.auto_include_screenshot.IsChecked = self.config.get('features', {}).get('include_screenshot', True)
        self.auto_include_context.IsChecked = self.config.get('features', {}).get('include_context', True)
        self.enable_actions.IsChecked = self.config.get('features', {}).get('enable_actions', True)
        self.enable_workflows.IsChecked = self.config.get('features', {}).get('enable_workflows', True)
        
        # Standards Source
        source = self.config.get('features', {}).get('standards_source', 'notion')
        if source == 'sharepoint':
            self.standards_source_combo.SelectedIndex = 1
            self.sharepoint_group.Visibility = System.Windows.Visibility.Visible
            self.notion_group.Visibility = System.Windows.Visibility.Collapsed
        else:
            self.standards_source_combo.SelectedIndex = 0
            self.sharepoint_group.Visibility = System.Windows.Visibility.Collapsed
            self.notion_group.Visibility = System.Windows.Visibility.Visible
            
        # SharePoint config
        sp_config = self.config.get('sharepoint', {})
        self.sharepoint_site_url.Text = sp_config.get('site_url', '')
        self.sharepoint_tenant_id.Text = sp_config.get('tenant_id', '')
        self.sharepoint_client_id.Text = sp_config.get('client_id', '')
        self.sharepoint_client_secret.Password = self.api_keys.get('sharepoint_client_secret', '')
        
        # API Keys
        self.notion_api_key.Text = self.api_keys.get('notion_api_key', '')
        self.anthropic_api_key.Text = self.api_keys.get('anthropic_api_key', '')
        
        # Notion config
        self.notion_database_id.Text = self.config.get('notion', {}).get('database_id', '')
        self.max_search_results.Text = str(self.config.get('notion', {}).get('max_search_results', 5))
        
        # Anthropic config
        self.model_name.Text = self.config.get('anthropic', {}).get('model', '')
        self.max_tokens.Text = str(self.config.get('anthropic', {}).get('max_tokens', 2048))
        self.temperature.Text = str(self.config.get('anthropic', {}).get('temperature', 0.7))
        
        # Logging
        self.logging_enabled.IsChecked = self.config.get('logging', {}).get('enabled', True)
        self.analytics_enabled.IsChecked = self.config.get('logging', {}).get('analytics_enabled', True)
        central_log = self.config.get('logging', {}).get('central_log_path', '')
        self.central_log_path.Text = central_log if central_log else ''
    
    def source_changed(self, sender, args):
        """Handle source selection change"""
        if self.standards_source_combo.SelectedIndex == 1: # SharePoint
            self.sharepoint_group.Visibility = System.Windows.Visibility.Visible
            self.notion_group.Visibility = System.Windows.Visibility.Collapsed
        else: # Notion
            self.sharepoint_group.Visibility = System.Windows.Visibility.Collapsed
            self.notion_group.Visibility = System.Windows.Visibility.Visible

    def save_click(self, sender, args):
        """Save button click handler"""
        try:
            # Update general settings
            if 'user' not in self.config:
                self.config['user'] = {}
            self.config['user']['name'] = self.user_name.Text.strip()
            self.config['user']['team'] = self.user_team.Text.strip()
            
            if 'features' not in self.config:
                self.config['features'] = {}
            self.config['features']['include_screenshot'] = bool(self.auto_include_screenshot.IsChecked)
            self.config['features']['include_context'] = bool(self.auto_include_context.IsChecked)
            self.config['features']['enable_actions'] = bool(self.enable_actions.IsChecked)
            self.config['features']['enable_workflows'] = bool(self.enable_workflows.IsChecked)
            
            # Update Standards Source
            if self.standards_source_combo.SelectedIndex == 1:
                self.config['features']['standards_source'] = 'sharepoint'
            else:
                self.config['features']['standards_source'] = 'notion'
                
            # Update SharePoint config
            if 'sharepoint' not in self.config:
                self.config['sharepoint'] = {}
            self.config['sharepoint']['site_url'] = self.sharepoint_site_url.Text
            self.config['sharepoint']['tenant_id'] = self.sharepoint_tenant_id.Text
            self.config['sharepoint']['client_id'] = self.sharepoint_client_id.Text
            
            # Update API keys
            self.api_keys['sharepoint_client_secret'] = self.sharepoint_client_secret.Password
            self.api_keys['notion_api_key'] = self.notion_api_key.Text
            self.api_keys['anthropic_api_key'] = self.anthropic_api_key.Text
            
            # Update Notion config
            if 'notion' not in self.config:
                self.config['notion'] = {}
            self.config['notion']['database_id'] = self.notion_database_id.Text
            try:
                self.config['notion']['max_search_results'] = int(self.max_search_results.Text)
            except ValueError:
                self.config['notion']['max_search_results'] = 5
            
            # Update Anthropic config
            if 'anthropic' not in self.config:
                self.config['anthropic'] = {}
            self.config['anthropic']['model'] = self.model_name.Text
            try:
                self.config['anthropic']['max_tokens'] = int(self.max_tokens.Text)
            except ValueError:
                self.config['anthropic']['max_tokens'] = 2048
            try:
                self.config['anthropic']['temperature'] = float(self.temperature.Text)
            except ValueError:
                self.config['anthropic']['temperature'] = 0.7
            
            # Update logging config
            if 'logging' not in self.config:
                self.config['logging'] = {}
            self.config['logging']['enabled'] = bool(self.logging_enabled.IsChecked)
            self.config['logging']['analytics_enabled'] = bool(self.analytics_enabled.IsChecked)
            central_log = self.central_log_path.Text.strip()
            if central_log:
                self.config['logging']['central_log_path'] = central_log
            
            # Save to files
            with open(self.api_keys_path, 'w') as f:
                json.dump(self.api_keys, f, indent=2)
            
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            forms.alert(
                "Settings saved successfully!",
                title="Success"
            )
            
            self.Close()
            
        except Exception as e:
            forms.alert(
                "Error saving settings:\n{}".format(str(e)),
                title="Error",
                warn_icon=True
            )
    
    def cancel_click(self, sender, args):
        """Cancel button click handler"""
        self.Close()
    
    def browse_log_path(self, sender, args):
        """Browse for central log path"""
        from pyrevit import forms
        folder = forms.pick_folder()
        if folder:
            self.central_log_path.Text = folder


def main():
    """Open settings dialog"""
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
