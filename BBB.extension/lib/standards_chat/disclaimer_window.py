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
        """
        Initialize disclaimer window.
        Set ``window._setup_needed = True`` after construction when the local
        venv hasn't been created yet so the install-prompt panel is shown after
        acceptance.  Defaults to False (install panel skipped).
        """
        try:
            # Create XAML path in ui folder
            # This file is in lib/standards_chat/, so up one level to lib, then to ui
            script_dir = os.path.dirname(__file__)
            lib_dir = os.path.dirname(script_dir)
            xaml_path = os.path.join(lib_dir, 'ui', 'disclaimer_window.xaml')
            
            # Initialize WPF window
            forms.WPFWindow.__init__(self, xaml_path)

            # True  → accepted + wants Kodama to set up & open now
            # False → accepted but wants to skip for now
            self.wants_to_launch = True
            # Overridden by caller when first-time venv setup is needed
            self._setup_needed = False
            
            # Load Kodama icon
            self._load_kodama_icon(lib_dir)
            
            # Wire up button events
            self.AcceptButton.Click   += self._accept_clicked
            self.DeclineButton.Click  += self._decline_clicked
            self.DctButton.Click      += self.dct_clicked
            self.SetupNowButton.Click += self._setup_now_clicked
            self.SkipInstallButton.Click += self._skip_install_clicked
            
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
    
    def show_install_panel_only(self):
        """
        Collapse the disclaimer text/buttons and show only the install panel.
        Call this before ShowDialog() when the disclaimer was already accepted
        on a prior launch but numpy has not been installed yet.
        """
        try:
            from System.Windows import Visibility
            self.DisclaimerScrollView.Visibility = Visibility.Collapsed
            self.DisclaimerButtonsBar.Visibility = Visibility.Collapsed
            self.InstallPanel.Visibility         = Visibility.Visible
        except Exception:
            pass  # if XAML names differ, window will show normally

    def _accept_clicked(self, sender, args):
        """I Understand clicked — show install panel if needed, otherwise close."""
        if getattr(self, '_setup_needed', False):
            try:
                from System.Windows import Visibility
                self.DisclaimerScrollView.Visibility  = Visibility.Collapsed
                self.DisclaimerButtonsBar.Visibility  = Visibility.Collapsed
                self.InstallPanel.Visibility          = Visibility.Visible
                return
            except Exception:
                pass  # fall through to immediate close on any error
        # Setup already done (or transition failed) — accept and close straight away
        self.wants_to_launch = True
        self.DialogResult = True
        self.Close()
    
    def _decline_clicked(self, sender, args):
        """Handle Decline button click - user declines terms"""
        try:
            self.DialogResult = False
            self.Close()
        except Exception as e:
            forms.alert("Error declining terms:\n{}".format(str(e)), 
                       title="Error", 
                       warn_icon=True)

    def _setup_now_clicked(self, sender, args):
        """Get Kodama ready — proceed with setup and open the chat when done."""
        try:
            self.wants_to_launch = True
            self.DialogResult = True
            self.Close()
        except Exception as e:
            forms.alert("Error:\n{}".format(str(e)), title="Error", warn_icon=True)

    def _skip_install_clicked(self, sender, args):
        """Not right now — accept disclaimer but don't open anything today."""
        try:
            self.wants_to_launch = False
            self.DialogResult = True
            self.Close()
        except Exception as e:
            forms.alert("Error:\n{}".format(str(e)), title="Error", warn_icon=True)

    # Keep old names as aliases so any external callers don't break
    def accept_clicked(self, sender, args):
        self._accept_clicked(sender, args)

    def decline_clicked(self, sender, args):
        self._decline_clicked(sender, args)
    
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
