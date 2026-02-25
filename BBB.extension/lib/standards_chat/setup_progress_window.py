# -*- coding: utf-8 -*-
"""
Setup Progress Toast Window
Non-modal bottom-right notification shown while the local venv is being created.
"""
import os
import sys
import time as _time

import clr
clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')
clr.AddReference('WindowsBase')

try:
    from typing import Any  # CPython 3.5+
except ImportError:
    Any = object  # type: ignore  # IronPython 2.7 fallback

from System.Windows import SystemParameters
from System.Windows.Media import SolidColorBrush, Color
from System.Windows.Threading import DispatcherTimer
from System import TimeSpan

from pyrevit import forms


class SetupProgressWindow(forms.WPFWindow):
    """
    Small toast window that polls a shared *status_dict* and updates itself.

    status_dict keys (written by the background thread):
        phase   : 'running' | 'done' | 'error'
        message : human-readable status string
        error   : error text (only when phase == 'error')

    When setup completes, the window shows 'Dismiss' and 'Launch Now' buttons
    instead of auto-closing.  If a *launch_callback* was registered via
    set_launch_callback(), clicking 'Launch Now' invokes it then closes the
    window.  If no callback is registered 'Launch Now' is hidden and only
    'Dismiss' is shown.
    """

    # Colours reused when showing final states
    _BLUE   = SolidColorBrush(Color.FromRgb(0,   120, 212))   # #0078D4
    _GREEN  = SolidColorBrush(Color.FromRgb(16,  124,  16))   # #107C10
    _RED    = SolidColorBrush(Color.FromRgb(168,   0,   0))   # #A80000
    _GREY   = SolidColorBrush(Color.FromRgb(96,   94,  92))   # #605E5C

    def __init__(self, status_dict):
        """
        Args:
            status_dict: The module-level dict in vector_db_interop that the
                         background thread updates.
        """
        script_dir = os.path.dirname(__file__)
        # This file lives in lib/standards_chat/; XAML is in lib/ui/
        lib_dir    = os.path.dirname(script_dir)
        xaml_path  = os.path.join(lib_dir, 'ui', 'setup_progress_window.xaml')

        forms.WPFWindow.__init__(self, xaml_path)

        self._status = status_dict
        self._dismissed = False
        self._launch_callback = None  # set via set_launch_callback()

        # Wire title-row close button (visible during running / error)
        self.DismissButton.Click += self._on_dismiss

        # Wire completion-state action buttons
        self.DismissActionButton.Click += self._on_dismiss_action
        self.LaunchNowButton.Click     += self._on_launch_now

        # Allow dragging by the title bar
        try:
            self.MouseLeftButtonDown += lambda s, e: self.DragMove()
        except Exception:
            pass

        # Re-position after layout pass so SizeToContent has resolved the height
        self.Loaded += lambda s, e: self._position_bottom_right()

        # Poll every 600 ms on the UI thread
        self._timer = DispatcherTimer()
        self._timer.Interval = TimeSpan.FromMilliseconds(600)
        self._timer.Tick     += self._on_tick
        self._timer.Start()

    # ------------------------------------------------------------------

    def _position_bottom_right(self):
        """Place the window in the bottom-right corner of the primary screen."""
        try:
            margin  = 20
            screen_w = SystemParameters.PrimaryScreenWidth
            screen_h = SystemParameters.PrimaryScreenHeight
            self.Left = screen_w  - self.Width  - margin
            self.Top  = screen_h - self.Height - margin - 40  # clear taskbar
        except Exception:
            pass  # centre-screen fallback (from XAML default) is fine

    def set_launch_callback(self, callback):
        """
        Register a callable to invoke when the user clicks 'Launch Now'.
        Safe to call after Show() — if setup already completed, the done
        state will be applied immediately on the next dispatcher tick.
        """
        self._launch_callback = callback
        # If setup already finished before the callback was registered,
        # show the completion UI straight away (avoid a 600 ms delay).
        try:
            if self._status.get('phase') in ('done', 'error'):
                self._apply_terminal_state(self._status.get('phase'))
        except Exception:
            pass

    def _on_dismiss(self, sender, args):
        """Hide the window (title-row X); setup continues in the background."""
        self._dismissed = True
        self._timer.Stop()
        self.Hide()

    def _on_dismiss_action(self, sender, args):
        """Close the window from the completion-state Dismiss button."""
        self._timer.Stop()
        self.Close()

    def _on_launch_now(self, sender, args):
        """Launch Kodama then close the window."""
        try:
            self.LaunchNowButton.IsEnabled = False
            if self._launch_callback is not None:
                self._launch_callback()
        except Exception:
            pass
        finally:
            self._timer.Stop()
            self.Close()

    def _on_tick(self, sender, args):
        """Called every 600 ms on the UI thread — read shared state and update UI."""
        try:
            phase   = self._status.get('phase',   'running')
            message = self._status.get('message', '')

            if phase in ('running', 'daemon_starting'):
                # Build status line with live elapsed time
                start = self._status.get('start_time')
                if start:
                    elapsed = int(_time.time() - start)
                    elapsed_str = u'  ({}s)'.format(elapsed)
                else:
                    elapsed_str = u''
                self.StatusText.Text = (message or u'Working\u2026') + elapsed_str
                return   # keep spinner going

            # Terminal state reached — stop polling and update UI
            self._timer.Stop()
            self._apply_terminal_state(phase)

        except Exception:
            # Never crash Revit over a notification widget
            pass

    def _apply_terminal_state(self, phase):
        """Update the window UI for a completed (done/error) state."""
        try:
            from System.Windows import Visibility

            if phase == 'done':
                self.SetupProgress.IsIndeterminate = False
                self.SetupProgress.Value           = 100
                self.SetupProgress.Foreground      = self._GREEN
                self.TitleText.Text                = u'Kodama \u2014 Ready to use \u2713'
                self.TitleText.Foreground          = self._GREEN
                self.StatusText.Text               = (
                    u'Everything is set up and good to go.'
                )
                self.StatusText.Foreground = self._GREY

                # Replace the title-bar X with the proper action buttons
                self.DismissButton.Visibility = Visibility.Collapsed
                # Hide "Launch Now" if no callback was registered
                if self._launch_callback is None:
                    self.LaunchNowButton.Visibility = Visibility.Collapsed
                self.ActionsPanel.Visibility = Visibility.Visible
                # Re-anchor to bottom-right now that the window is taller
                self.UpdateLayout()
                self._position_bottom_right()

            elif phase == 'error':
                self.SetupProgress.IsIndeterminate = False
                self.SetupProgress.Value           = 0
                self.SetupProgress.Foreground      = self._RED
                self.TitleText.Text                = u'Kodama \u2014 Setup ran into a problem'
                self.TitleText.Foreground          = self._RED
                err = self._status.get('error', 'Unknown error')
                self.StatusText.Text = (
                    u'Something went wrong during setup. '
                    u'Details: {}  '
                    u'Check the debug log for more information.'.format(err[:100])
                )
                self.StatusText.Foreground = self._RED
                # Keep the title-bar X so the user can close after reading

        except Exception:
            pass

    def _auto_close(self):
        # Kept for compatibility but no longer used
        try:
            self.Close()
        except Exception:
            pass

