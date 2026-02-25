# -*- coding: utf-8 -*-
"""
DB Update Prompt Window
Modal dialog shown mid-session (after a search completes) when a newer version
of the standards database is available on the network share.

The user can choose:
  "Sync Now"  – sync starts immediately in the background; a toast window
                shows progress.
  "Later"     – dismissed for the rest of the session; next launch will
                auto-sync at startup instead.
"""
import os

import clr
clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')
clr.AddReference('WindowsBase')

from pyrevit import forms


class DBUpdatePromptWindow(forms.WPFWindow):
    """
    Simple modal prompt asking whether to sync the standards DB now or later.

    After ``ShowDialog()`` inspect ``self.sync_now`` to determine the choice:
        True  – user clicked "Sync Now"
        False – user clicked "Later" or closed the window
    """

    def __init__(self):
        script_dir = os.path.dirname(__file__)
        lib_dir    = os.path.dirname(script_dir)   # lib/standards_chat/ → lib/
        xaml_path  = os.path.join(lib_dir, 'ui', 'db_update_prompt_window.xaml')

        forms.WPFWindow.__init__(self, xaml_path)

        self.sync_now = False

        self.SyncNowButton.Click += self._on_sync_now
        self.LaterButton.Click   += self._on_later

    def _on_sync_now(self, sender, args):
        self.sync_now     = True
        self.DialogResult = True
        self.Close()

    def _on_later(self, sender, args):
        self.sync_now     = False
        self.DialogResult = False
        self.Close()
