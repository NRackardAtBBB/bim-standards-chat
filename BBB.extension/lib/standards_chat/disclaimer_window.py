# -*- coding: utf-8 -*-
"""
Disclaimer Window Logic
Shows first-time user disclaimer with terms of use
"""

from pyrevit import forms
import os
import webbrowser
import System

class DisclaimerWindow(forms.WPFWindow):
    """First-time user disclaimer window"""
    
    def __init__(self):
        """Initialize disclaimer window"""
        try:
            # Create XAML path in ui folder
            # This file is in lib/standards_chat/, so up one level to lib, then to ui
            script_dir = os.path.dirname(__file__)
            lib_dir = os.path.dirname(script_dir)
            xaml_path = os.path.join(lib_dir, 'ui', 'disclaimer_window.xaml')
            
            # Initialize WPF window
            forms.WPFWindow.__init__(self, xaml_path)
            
            # Load Kodama icon
            self._load_kodama_icon(lib_dir)
            
            # Wire up button events
            self.AcceptButton.Click += self.accept_clicked
            self.DeclineButton.Click += self.decline_clicked
            self.DctButton.Click += self.dct_clicked
            
            # Wire up hyperlink
            self.LearnMoreLink.Click += self.learn_more_clicked
            
        except Exception as e:
            forms.alert("Failed to load disclaimer window:\n{}".format(str(e)), 
                       title="Error", 
                       warn_icon=True)
            raise
    
    def _load_kodama_icon(self, lib_dir):
        """Load and set the Kodama icon"""
        try:
            from System.Windows.Media.Imaging import BitmapImage
            kodama_icon_path = os.path.join(lib_dir, 'ui', 'avatars', 'Kodama.png')
            
            if os.path.exists(kodama_icon_path):
                bmp = BitmapImage()
                bmp.BeginInit()
                bmp.UriSource = System.Uri(kodama_icon_path)
                bmp.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad
                bmp.EndInit()
                self.KodamaIcon.Source = bmp
        except Exception:
            # If icon fails to load, just continue without it
            pass
    
    def accept_clicked(self, sender, args):
        """Handle Accept button click - user agrees to terms"""
        try:
            self.DialogResult = True
            self.Close()
        except Exception as e:
            forms.alert("Error accepting terms:\n{}".format(str(e)), 
                       title="Error", 
                       warn_icon=True)
    
    def decline_clicked(self, sender, args):
        """Handle Decline button click - user declines terms"""
        try:
            self.DialogResult = False
            self.Close()
        except Exception as e:
            forms.alert("Error declining terms:\n{}".format(str(e)), 
                       title="Error", 
                       warn_icon=True)
    
    def dct_clicked(self, sender, args):
        """Handle DCT button click - open ticket submission URL"""
        try:
            dct_url = "https://portal.bbbarch.com/a/tickets/new"
            webbrowser.open(dct_url)
            # Keep window open so user can still read terms
        except Exception as e:
            forms.alert("Failed to open DCT ticket page:\n{}".format(str(e)), 
                       title="Error", 
                       warn_icon=True)
    
    def learn_more_clicked(self, sender, args):
        """Handle Learn More hyperlink click - open Kodama intranet page"""
        try:
            intranet_url = "https://beyerblinderbelle.sharepoint.com/sites/revitstandards/SitePages/Kodama.aspx"
            webbrowser.open(intranet_url)
            # Keep window open so user can still read terms
        except Exception as e:
            forms.alert("Failed to open intranet page:\n{}".format(str(e)), 
                       title="Error", 
                       warn_icon=True)
