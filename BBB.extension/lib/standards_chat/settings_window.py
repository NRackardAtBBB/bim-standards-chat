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

        # Admin unlock state
        self._admin_unlocked = False
        
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

        # Auto-unlock admin panel for whitelisted users (no password needed)
        if self._is_admin_user():
            self._unlock_admin()
        
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
        self._update_local_env_status()

        # Search thresholds
        vs_config = self.config.get('vector_search', {})
        self.similarity_threshold.Text = str(vs_config.get('similarity_threshold', 0.5))
        self.confidence_threshold.Text = str(vs_config.get('confidence_threshold', 0.5))
    
    def source_changed(self, sender, args):
        """Handle source selection change"""
        if self.standards_source_combo.SelectedIndex == 1: # SharePoint
            self.sharepoint_group.Visibility = System.Windows.Visibility.Visible
            self.notion_group.Visibility = System.Windows.Visibility.Collapsed
        else: # Notion
            self.sharepoint_group.Visibility = System.Windows.Visibility.Collapsed
            self.notion_group.Visibility = System.Windows.Visibility.Visible
    
    def _is_admin_user(self):
        """Check if current Windows user is in the admin whitelist (stored in api_keys.json)"""
        # admin_whitelist lives in api_keys.json (gitignored) so it is never committed to the repo.
        # Falls back to developer_whitelist in config.json for backwards compatibility.
        whitelist = self.api_keys.get('admin_whitelist', None)
        if whitelist is None:
            whitelist = self.config.get('vector_search', {}).get('developer_whitelist', [])
        current_user = os.environ.get('USERNAME', '').lower()
        return current_user in [u.lower() for u in whitelist]

    def _unlock_admin(self):
        """Reveal admin panel and update button UI"""
        self._admin_unlocked = True
        self.admin_panel.Visibility = System.Windows.Visibility.Visible
        self.unlock_admin_btn.Visibility = System.Windows.Visibility.Collapsed
        self.admin_unlocked_label.Visibility = System.Windows.Visibility.Visible

    def unlock_admin_click(self, sender, args):
        """Handle Admin Settings button click"""
        # Whitelisted users bypass the password
        if self._is_admin_user():
            self._unlock_admin()
            return

        entered = self._prompt_admin_password()
        if entered is None:
            return  # User cancelled

        admin_password = self.config.get('admin', {}).get('password', '')
        if entered == admin_password:
            self._unlock_admin()
        else:
            forms.alert("Incorrect password.", title="Admin Access", warn_icon=True)

    def _prompt_admin_password(self):
        """Show a modal password dialog. Returns the entered string, or None if cancelled."""
        import System.Windows as SW
        import System.Windows.Controls as SWC

        result = [None]

        dialog = SW.Window()
        dialog.Title = "Admin Access"
        dialog.Width = 300
        dialog.Height = 180
        dialog.WindowStartupLocation = SW.WindowStartupLocation.CenterOwner
        dialog.ResizeMode = SW.ResizeMode.NoResize
        try:
            dialog.Owner = self
        except Exception:
            pass

        outer = SWC.StackPanel()
        outer.Margin = SW.Thickness(20)

        lbl = SWC.TextBlock()
        lbl.Text = "Enter admin password:"
        lbl.Margin = SW.Thickness(0, 0, 0, 8)

        pw_box = SWC.PasswordBox()
        pw_box.Margin = SW.Thickness(0, 0, 0, 12)

        btn_panel = SWC.StackPanel()
        btn_panel.Orientation = SWC.Orientation.Horizontal
        btn_panel.HorizontalAlignment = SW.HorizontalAlignment.Right

        ok_btn = SWC.Button()
        ok_btn.Content = "OK"
        ok_btn.Width = 70
        ok_btn.Margin = SW.Thickness(0, 0, 5, 0)
        ok_btn.IsDefault = True

        cancel_btn = SWC.Button()
        cancel_btn.Content = "Cancel"
        cancel_btn.Width = 70
        cancel_btn.IsCancel = True

        def ok_click(s, e):
            result[0] = pw_box.Password
            dialog.DialogResult = True

        def cancel_click(s, e):
            dialog.DialogResult = False

        ok_btn.Click += ok_click
        cancel_btn.Click += cancel_click

        btn_panel.Children.Add(ok_btn)
        btn_panel.Children.Add(cancel_btn)
        outer.Children.Add(lbl)
        outer.Children.Add(pw_box)
        outer.Children.Add(btn_panel)
        dialog.Content = outer
        dialog.ShowDialog()

        return result[0]

    def _update_vector_search_visibility(self):
        """Show/hide vector search details section based on the enable checkbox"""
        if self.enable_vector_search.IsChecked:
            self.vector_search_group.Visibility = System.Windows.Visibility.Visible
        else:
            self.vector_search_group.Visibility = System.Windows.Visibility.Collapsed
    
    def _update_local_env_status(self):
        """Refresh the local environment status label in the admin panel."""
        try:
            from standards_chat.vector_db_interop import get_local_env_status
            info = get_local_env_status()
            self.local_env_status_text.Text = (
                u'{message}\nPython: {python}'.format(**info)
            )
        except Exception as exc:
            self.local_env_status_text.Text = u'Status unavailable: {}'.format(exc)

    def reset_local_venv_click(self, sender, args):
        """Delete local venv so setup re-runs on next Kodama launch."""
        if not forms.alert(
            'This will delete the local Python environment for this machine.\n\n'
            'Setup will run automatically the next time you open Kodama.\n\nContinue?',
            title='Reset Local Environment',
            yes=True, no=True
        ):
            return
        try:
            from standards_chat.vector_db_interop import reset_local_env
            ok, msg = reset_local_env(rebuild=False)
            self._update_local_env_status()
            forms.alert(msg, title='Local Environment Reset' if ok else 'Error',
                        warn_icon=not ok)
        except Exception as exc:
            forms.alert('Error: {}'.format(exc), title='Error', warn_icon=True)

    def rebuild_local_venv_click(self, sender, args):
        """Delete local venv and immediately kick off a background rebuild."""
        if not forms.alert(
            'This will delete and immediately rebuild the local Python environment.\n\n'
            'A progress notification will appear while setup runs in the background.\n\nContinue?',
            title='Reset & Rebuild Local Environment',
            yes=True, no=True
        ):
            return
        try:
            from standards_chat.vector_db_interop import reset_local_env
            ok, msg = reset_local_env(rebuild=True)
            self._update_local_env_status()
            forms.alert(msg, title='Local Environment' if ok else 'Error',
                        warn_icon=not ok)
        except Exception as exc:
            forms.alert('Error: {}'.format(exc), title='Error', warn_icon=True)

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

            # Run the full SharePoint → vector DB sync as a background subprocess
            from standards_chat.vector_db_interop import _PYREVIT_PYTHON, debug_log
            import subprocess as _sp
            import os as _os

            sync_script = _os.path.join(
                _os.path.dirname(_os.path.abspath(__file__)), 'sync_vector_db.py'
            )

            if not _PYREVIT_PYTHON:
                forms.alert(
                    "Cannot run re-index: pyRevit CPython not found.\n"
                    "Make sure pyRevit is installed.",
                    title="Error", warn_icon=True
                )
                return

            _sp.Popen(
                [_PYREVIT_PYTHON, sync_script],
                stdout=_sp.PIPE, stderr=_sp.PIPE,
                shell=False, creationflags=0x08000000
            )
            debug_log("reindex_vector_db_click: launched sync_vector_db.py subprocess")

            forms.alert(
                "Re-index started in the background.\n\n"
                "The vector database will be rebuilt from the latest SharePoint content.\n"
                "This may take a few minutes.",
                title="Re-index Started"
            )

            # Update stats UI
            self.load_settings()
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
            
            # User-facing feature toggles (always saved)
            if 'features' not in self.config:
                self.config['features'] = {}
            self.config['features']['include_screenshot'] = bool(self.auto_include_screenshot.IsChecked)
            self.config['features']['include_context'] = bool(self.auto_include_context.IsChecked)

            # Admin-only settings: only written when admin panel is unlocked
            if self._admin_unlocked:
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

                # Update search thresholds
                if 'vector_search' not in self.config:
                    self.config['vector_search'] = {}
                try:
                    self.config['vector_search']['similarity_threshold'] = float(self.similarity_threshold.Text)
                    self.config['vector_search']['confidence_threshold'] = float(self.confidence_threshold.Text)
                except Exception:
                    pass

                self.config_manager.save_api_keys()

            # Save using ConfigManager (always saves user prefs; api_keys only if admin unlocked)
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
