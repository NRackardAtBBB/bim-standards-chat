# -*- coding: utf-8 -*-
"""
Settings Window Logic
Manages the settings dialog for API keys and configuration
"""

from pyrevit import forms
import sys
import os
import json
import System

from standards_chat.history_manager import HistoryManager
from standards_chat.config_manager import ConfigManager

class SettingsWindow(forms.WPFWindow):
    """Settings configuration window"""
    
    def __init__(self, config_dir):
        """Initialize settings window"""
        # config_dir argument is kept for compatibility but we rely on ConfigManager
        self.config_dir = config_dir
        
        # Initialize Config Manager
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        self.api_keys = self.config_manager.api_keys
        
        # Create XAML path in ui folder
        # This file is in lib/standards_chat/, so up one level to lib, then to ui
        script_dir = os.path.dirname(__file__)
        lib_dir = os.path.dirname(script_dir)
        
        xaml_path = os.path.join(lib_dir, 'ui', 'settings_window.xaml')
        self.avatars_dir = os.path.join(lib_dir, 'ui', 'avatars')
        
        forms.WPFWindow.__init__(self, xaml_path)
        
        # Wire up reset disclaimer button (for module caching compatibility)
        if hasattr(self, 'reset_disclaimer_btn'):
            self.reset_disclaimer_btn.Click += self.reset_disclaimer_click
        
        # Populate fields with current values
        self.populate_fields()
        
    def populate_avatars(self):
        """Populate avatar combo box"""
        from System.Windows.Controls import ComboBoxItem
        
        self.avatar_combo.Items.Clear()
        
        # Default option
        default_item = ComboBoxItem()
        default_item.Content = "None (Use Initials)"
        default_item.Tag = None
        self.avatar_combo.Items.Add(default_item)
        
        # Scan folder
        selected_index = 0
        current_avatar = self.config.get('user', {}).get('avatar', None)
        
        if os.path.exists(self.avatars_dir):
            files = [f for f in os.listdir(self.avatars_dir) if f.lower().endswith('.png')]
            valid_files = [f for f in files if f.lower() != 'kodama.png']
            
            for i, f in enumerate(valid_files):
                item = ComboBoxItem()
                # Remove extension for display
                display_name = f
                if display_name.lower().endswith('.png'):
                    display_name = display_name[:-4]
                    
                item.Content = display_name
                item.Tag = f
                self.avatar_combo.Items.Add(item)
                
                if current_avatar == f:
                    # Account for default item (index 0)
                    selected_index = self.avatar_combo.Items.Count - 1
                    
        self.avatar_combo.SelectedIndex = selected_index

    def avatar_selection_changed(self, sender, args):
        """Handle avatar selection change"""
        try:
            from System.Windows.Media.Imaging import BitmapImage
            from System import Uri
            
            selected_item = self.avatar_combo.SelectedItem
            if not selected_item or not selected_item.Tag:
                self.avatar_preview.Source = None
                return
                
            filename = selected_item.Tag
            path = os.path.join(self.avatars_dir, filename)
            
            if os.path.exists(path):
                img = BitmapImage()
                img.BeginInit()
                img.UriSource = Uri("file:///" + path.replace("\\", "/"))
                img.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad
                img.EndInit()
                self.avatar_preview.Source = img
        except Exception:
            self.avatar_preview.Source = None
    
    def load_settings(self):
        """Load current settings via ConfigManager"""
        try:
            # Reload from disk
            self.config_manager = ConfigManager()
            self.config = self.config_manager.config
            self.api_keys = self.config_manager.api_keys
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
        # Avatars
        self.populate_avatars()

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
        
        # Vector Search (Developer Only)
        self.enable_vector_search.IsChecked = self.config.get('features', {}).get('enable_vector_search', False)
        self._update_vector_search_visibility()
        self._update_vector_search_stats()
    
    def source_changed(self, sender, args):
        """Handle source selection change"""
        if self.standards_source_combo.SelectedIndex == 1: # SharePoint
            self.sharepoint_group.Visibility = System.Windows.Visibility.Visible
            self.notion_group.Visibility = System.Windows.Visibility.Collapsed
        else: # Notion
            self.sharepoint_group.Visibility = System.Windows.Visibility.Collapsed
            self.notion_group.Visibility = System.Windows.Visibility.Visible
    
    def _is_developer_user(self):
        """Check if current user is in developer whitelist"""
        whitelist = self.config.get('vector_search', {}).get('developer_whitelist', [])
        current_user = os.environ.get('USERNAME', '').lower()
        return current_user in [u.lower() for u in whitelist]
    
    def _update_vector_search_visibility(self):
        """Show/hide vector search section based on developer mode and user"""
        developer_mode = self.config.get('vector_search', {}).get('developer_mode', True)
        
        # Show section if developer mode is OFF, or if user is in whitelist
        if not developer_mode or self._is_developer_user():
            # Show the main checkbox
            self.enable_vector_search.Visibility = System.Windows.Visibility.Visible
            # Show the detailed section if checkbox is checked
            if self.enable_vector_search.IsChecked:
                self.vector_search_group.Visibility = System.Windows.Visibility.Visible
            else:
                self.vector_search_group.Visibility = System.Windows.Visibility.Collapsed
        else:
            # Hide everything if developer mode is on and user not in whitelist
            self.enable_vector_search.Visibility = System.Windows.Visibility.Collapsed
            self.vector_search_group.Visibility = System.Windows.Visibility.Collapsed
    
    def _update_vector_search_stats(self):
        """Update vector search statistics display"""
        vs_config = self.config.get('vector_search', {})
        last_sync = vs_config.get('last_sync_timestamp')
        doc_count = vs_config.get('indexed_document_count', 0)
        chunk_count = vs_config.get('indexed_chunk_count', 0)
        pdf_count = vs_config.get('indexed_pdf_count', 0)
        pdf_failed = vs_config.get('failed_pdf_count', 0)
        video_count = vs_config.get('indexed_video_count', 0)
        video_failed = vs_config.get('failed_video_count', 0)
        
        # Calculate page count (total docs minus PDFs and videos)
        page_count = doc_count - pdf_count - video_count
        
        # Display document counts with breakdown
        if pdf_count > 0 or video_count > 0:
            doc_text = "{} ({} pages".format(doc_count, page_count)
            if pdf_count > 0:
                doc_text += ", {} PDFs".format(pdf_count)
            if video_count > 0:
                doc_text += ", {} videos".format(video_count)
            if pdf_failed > 0 or video_failed > 0:
                total_failed = pdf_failed + video_failed
                doc_text += ", {} failed".format(total_failed)
            doc_text += ")"
            self.indexed_docs_text.Text = doc_text
        else:
            self.indexed_docs_text.Text = str(doc_count)
        
        self.indexed_chunks_text.Text = str(chunk_count)
        
        if last_sync:
            from datetime import datetime
            try:
                sync_time = datetime.fromisoformat(last_sync)
                self.sync_status_text.Text = "Last synced: {}".format(sync_time.strftime("%Y-%m-%d %H:%M:%S"))
            except:
                self.sync_status_text.Text = "Last synced: {}".format(last_sync)
        else:
            self.sync_status_text.Text = "Not synced yet"
    
    def vector_search_checked(self, sender, args):
        """Handle vector search checkbox checked"""
        self._update_vector_search_visibility()
    
    def vector_search_unchecked(self, sender, args):
        """Handle vector search checkbox unchecked"""
        self._update_vector_search_visibility()
    
    def _save_config_to_disk(self):
        """Save current settings to disk without closing dialog"""
        # Update SharePoint config
        if 'sharepoint' not in self.config:
            self.config['sharepoint'] = {}
        self.config['sharepoint']['site_url'] = self.sharepoint_site_url.Text
        self.config['sharepoint']['tenant_id'] = self.sharepoint_tenant_id.Text
        self.config['sharepoint']['client_id'] = self.sharepoint_client_id.Text
        
        # Update API keys
        self.api_keys['sharepoint_client_secret'] = self.sharepoint_client_secret.Password
        self.api_keys['anthropic_api_key'] = self.anthropic_api_key.Text
        
        # Update features
        if 'features' not in self.config:
            self.config['features'] = {}
        if self.standards_source_combo.SelectedIndex == 1:
            self.config['features']['standards_source'] = 'sharepoint'
        
        # Save via ConfigManager
        self.config_manager.save_api_keys()
        self.config_manager.save()

    def clear_history_click(self, sender, args):
        """Clear all chat history"""
        if forms.alert("Are you sure you want to delete all chat history? This cannot be undone.", 
                      title="Confirm Delete", 
                      yes=True, no=True):
            try:
                history_manager = HistoryManager()
                count = history_manager.clear_all_sessions()
                forms.alert("Deleted {} chat sessions.".format(count), title="Success")
            except Exception as e:
                forms.alert("Error clearing history: {}".format(str(e)), title="Error")

    def reset_disclaimer_click(self, sender, args):
        """Reset disclaimer acceptance so it shows again on next launch"""
        if forms.alert("This will reset your acceptance of the terms and conditions. The disclaimer will appear again the next time you launch Kodama.\n\nContinue?", 
                      title="Reset Terms Acceptance", 
                      yes=True, no=True):
            try:
                # Remove disclaimer acceptance flags
                if 'user' in self.config:
                    if 'has_seen_disclaimer' in self.config['user']:
                        del self.config['user']['has_seen_disclaimer']
                    if 'disclaimer_accepted_date' in self.config['user']:
                        del self.config['user']['disclaimer_accepted_date']
                    if 'disclaimer_version' in self.config['user']:
                        del self.config['user']['disclaimer_version']
                
                # Save changes
                self.config_manager.save()
                forms.alert("Terms acceptance has been reset. The disclaimer will appear the next time you launch Kodama.", 
                           title="Success")
            except Exception as e:
                forms.alert("Error resetting disclaimer: {}".format(str(e)), 
                           title="Error", 
                           warn_icon=True)

    def update_index_click(self, sender, args):
        """Update SharePoint search index"""
        try:
            # 1. Save current settings to disk (so ConfigManager picks them up)
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
            self.api_keys['anthropic_api_key'] = self.anthropic_api_key.Text
            
            # Save via ConfigManager
            self.config_manager.save_api_keys()
            self.config_manager.save()
            
            # 2. Initialize Client
            from standards_chat.config_manager import ConfigManager
            config_manager = ConfigManager()
            
            from standards_chat.sharepoint_client import SharePointClient
            client = SharePointClient(config_manager)
            
            # 3. Fetch Index
            System.Windows.Input.Mouse.OverrideCursor = System.Windows.Input.Cursors.Wait
            
            try:
                pages = client.get_all_pages_metadata()
            finally:
                System.Windows.Input.Mouse.OverrideCursor = None
            
            if not pages:
                forms.alert("No pages found or error connecting to SharePoint.\nCheck your credentials and site URL.", title="Error")
                return
                
            # 4. Save Index
            index_path = os.path.join(self.config_dir, 'sharepoint_index.json')
            f = None
            try:
                f = open(index_path, 'w')
                json.dump(pages, f, indent=2)
            finally:
                if f:
                    try:
                        f.close()
                    except:
                        pass
                
            forms.alert(
                "Successfully indexed {} pages.\n\nThe search assistant will now use this index to find better results.".format(len(pages)),
                title="Index Updated"
            )
            
        except Exception as e:
            System.Windows.Input.Mouse.OverrideCursor = None
            forms.alert(
                "Error updating index:\n{}".format(str(e)),
                title="Error",
                warn_icon=True
            )
    
    def reindex_vector_db_click(self, sender, args):
        """Re-index vector database with current SharePoint content"""
        try:
            # Confirm action
            if not forms.alert(
                "This will rebuild the vector database from scratch using the latest SharePoint content.\n\n"
                "This may take a few minutes. Continue?",
                title="Confirm Re-index",
                yes=True,
                no=True
            ):
                return
            
            # Save current settings first
            self._save_config_to_disk()
            
            # Show progress
            System.Windows.Input.Mouse.OverrideCursor = System.Windows.Input.Cursors.Wait
            
            # Use sync script approach to avoid freezing
            # In a real app we'd use a background thread, but for now we'll run inline
            # We need to import the sync tool
            from standards_chat.sync_vector_db import VectorDBSycner
            
            # Re-initialize config manager with potentially new settings
            from standards_chat.config_manager import ConfigManager
            config_manager = ConfigManager()
            
            syncer = VectorDBSycner(config_manager)
            
            # Run sync
            stats = syncer.sync_all(force_rebuild=True)
            
            # Show results
            msg = "Re-index complete!\n\nDocuments processed: {}\nChunks generated: {}\nDuration: {:.1f}s".format(
                stats['documents_processed'],
                stats['chunks_generated'],
                stats['duration_seconds']
            )
            
            forms.alert(msg, title="Success")
            
            # Update stats UI
            self.load_settings() # Reload config to get new stats
            self._update_vector_search_stats()
                    
        except Exception as e:
            forms.alert(
                "Error during re-indexing:\n{}".format(str(e)),
                title="Error",
                warn_icon=True
            )
            import traceback
            traceback.print_exc()
            
        finally:
            System.Windows.Input.Mouse.OverrideCursor = None

    def save_click(self, sender, args):
        """Save button click handler"""
        try:
            # Update general settings
            if 'user' not in self.config:
                self.config['user'] = {}
            self.config['user']['name'] = self.user_name.Text.strip()
            self.config['user']['team'] = self.user_team.Text.strip()
            
            # Save avatar
            selected_item = self.avatar_combo.SelectedItem
            if selected_item and selected_item.Tag:
                self.config['user']['avatar'] = selected_item.Tag
            else:
                self.config['user']['avatar'] = None
            
            if 'features' not in self.config:
                self.config['features'] = {}
            self.config['features']['include_screenshot'] = bool(self.auto_include_screenshot.IsChecked)
            self.config['features']['include_context'] = bool(self.auto_include_context.IsChecked)
            self.config['features']['enable_actions'] = bool(self.enable_actions.IsChecked)
            self.config['features']['enable_workflows'] = bool(self.enable_workflows.IsChecked)
            self.config['features']['enable_vector_search'] = bool(self.enable_vector_search.IsChecked)
            
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
            except:
                pass
                
            # Update Anthropic config
            if 'anthropic' not in self.config:
                self.config['anthropic'] = {}
            self.config['anthropic']['model'] = self.model_name.Text
            try:
                self.config['anthropic']['max_tokens'] = int(self.max_tokens.Text)
                self.config['anthropic']['temperature'] = float(self.temperature.Text)
            except:
                pass
            
            # Update Logging
            if 'logging' not in self.config:
                self.config['logging'] = {}
            self.config['logging']['enabled'] = bool(self.logging_enabled.IsChecked)
            self.config['logging']['analytics_enabled'] = bool(self.analytics_enabled.IsChecked)
            self.config['logging']['central_log_path'] = self.central_log_path.Text.strip()

            # Save using ConfigManager
            self.config_manager.save_api_keys()
            self.config_manager.save()
            
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
        folder = forms.pick_folder()
        if folder:
            self.central_log_path.Text = folder
