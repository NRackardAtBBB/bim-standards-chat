# -*- coding: utf-8 -*-
"""
DB Update Progress Window
Bottom-right toast (or centered startup window) shown while the local vector
DB cache is being refreshed from the network share.

Two display modes:
  startup=True  – centered on screen; shows an "Open Kodama" button when done
                  so the user can launch the chat window once sync finishes.
  startup=False – bottom-right toast; auto-closes 3 seconds after done.
"""
import os
import time as _time

import clr
clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')
clr.AddReference('WindowsBase')

from System.Windows import SystemParameters, Visibility, WindowStartupLocation
from System.Windows.Media import SolidColorBrush, Color
from System.Windows.Threading import DispatcherTimer
from System import TimeSpan

from pyrevit import forms


class DBUpdateWindow(forms.WPFWindow):
    """
    Progress window for the vector DB cache sync operation.

    Accepts the module-level ``_db_sync_status`` dict from
    ``vector_db_interop`` and polls it every 600 ms via a DispatcherTimer.

    Args:
        status_dict  : The shared status dict (same threading model as
                       SetupProgressWindow — GIL-atomic dict updates).
        startup      : If True the window is centered and shows an
                       "Open Kodama" button when sync completes.
                       If False it appears as a bottom-right toast and
                       auto-closes 3 s after reaching the done state.
        launch_callback : Optional callable invoked when the user clicks
                          "Open Kodama" (startup mode only).
    """

    _BLUE  = SolidColorBrush(Color.FromRgb(0,   120, 212))   # #0078D4
    _GREEN = SolidColorBrush(Color.FromRgb(16,  124,  16))   # #107C10
    _RED   = SolidColorBrush(Color.FromRgb(168,   0,   0))   # #A80000
    _GREY  = SolidColorBrush(Color.FromRgb(96,   94,  92))   # #605E5C

    def __init__(self, status_dict, startup=False, launch_callback=None):
        script_dir = os.path.dirname(__file__)
        lib_dir    = os.path.dirname(script_dir)   # lib/standards_chat/ → lib/
        xaml_path  = os.path.join(lib_dir, 'ui', 'db_update_window.xaml')

        forms.WPFWindow.__init__(self, xaml_path)

        self._status          = status_dict
        self._startup         = startup
        self._launch_callback = launch_callback
        self._done_since      = None   # timestamp when phase reached 'done' (toast auto-close)

        # Wire buttons
        self.DismissButton.Click       += self._on_dismiss
        self.DismissActionButton.Click += self._on_dismiss_action
        self.OpenKodamaButton.Click    += self._on_open_kodama

        # Draggable (toast only — centered window doesn't need it but it's harmless)
        try:
            self.MouseLeftButtonDown += lambda s, e: self.DragMove()
        except Exception:
            pass

        # Position on Loaded (after SizeToContent resolves the height)
        self.Loaded += self._on_loaded

        # Poll status every 600 ms
        self._timer = DispatcherTimer()
        self._timer.Interval = TimeSpan.FromMilliseconds(600)
        self._timer.Tick     += self._on_tick
        self._timer.Start()

    # ------------------------------------------------------------------
    # Positioning
    # ------------------------------------------------------------------

    def _on_loaded(self, sender, args):
        if self._startup:
            # Centre on screen — let WPF handle it after we override the
            # Manual placement that the XAML default sets.
            self.WindowStartupLocation = WindowStartupLocation.CenterScreen
            # Force re-apply (layout already happened; nudge into centre)
            try:
                from System.Windows import SystemParameters as _sp
                self.Left = (_sp.PrimaryScreenWidth  - self.ActualWidth)  / 2
                self.Top  = (_sp.PrimaryScreenHeight - self.ActualHeight) / 2
            except Exception:
                pass
        else:
            self._position_bottom_right()

    def _position_bottom_right(self):
        try:
            margin   = 20
            screen_w = SystemParameters.PrimaryScreenWidth
            screen_h = SystemParameters.PrimaryScreenHeight
            self.Left = screen_w - self.Width  - margin
            self.Top  = screen_h - self.Height - margin - 40  # clear taskbar
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_dismiss(self, sender, args):
        """Title-row ✕ — hide so sync continues but stop polling."""
        self._timer.Stop()
        if self._startup:
            # In startup mode dismiss means "I'll open Kodama myself later"
            self.Close()
        else:
            self.Hide()

    def _on_dismiss_action(self, sender, args):
        """Completion-state Dismiss button — proper close."""
        self._timer.Stop()
        self.Close()

    def _on_open_kodama(self, sender, args):
        """Open Kodama button (startup mode) — invoke callback then close."""
        try:
            self.OpenKodamaButton.IsEnabled = False
            if self._launch_callback is not None:
                self._launch_callback()
        except Exception:
            pass
        finally:
            self._timer.Stop()
            self.Close()

    # ------------------------------------------------------------------
    # Timer tick
    # ------------------------------------------------------------------

    def _on_tick(self, sender, args):
        try:
            phase   = self._status.get('phase',   'syncing')
            message = self._status.get('message', u'')

            if phase == 'syncing':
                start = self._status.get('start_time')
                if start:
                    elapsed     = int(_time.time() - start)
                    elapsed_str = u'  ({}s)'.format(elapsed)
                else:
                    elapsed_str = u''
                self.StatusText.Text = (message or u'Syncing\u2026') + elapsed_str
                return   # keep spinner going

            # Terminal state — stop polling and update UI
            self._timer.Stop()
            self._apply_terminal_state(phase)

        except Exception:
            pass

    # ------------------------------------------------------------------
    # Terminal-state UI update
    # ------------------------------------------------------------------

    def _apply_terminal_state(self, phase):
        try:
            if phase == 'done':
                self.SyncProgress.IsIndeterminate = False
                self.SyncProgress.Value           = 100
                self.SyncProgress.Foreground      = self._GREEN
                self.TitleText.Text               = u'Kodama \u2014 Standards Up to Date \u2713'
                self.TitleText.Foreground         = self._GREEN
                self.StatusText.Text              = (
                    u'The standards database has been refreshed. '
                    u'Your next search will use the latest content.'
                )
                self.StatusText.Foreground = self._GREY

                # Hide title-bar X; show action buttons
                self.DismissButton.Visibility = Visibility.Collapsed
                if self._startup and self._launch_callback is not None:
                    self.OpenKodamaButton.Visibility = Visibility.Visible
                self.ActionsPanel.Visibility = Visibility.Visible

                self.UpdateLayout()
                if not self._startup:
                    self._position_bottom_right()
                    # Auto-close toast after 3 s
                    self._done_since = _time.time()
                    self._start_auto_close_timer()

            elif phase == 'error':
                self.SyncProgress.IsIndeterminate = False
                self.SyncProgress.Value           = 0
                self.SyncProgress.Foreground      = self._RED
                self.TitleText.Text               = u'Kodama \u2014 Sync encountered a problem'
                self.TitleText.Foreground         = self._RED
                err = self._status.get('error', 'Unknown error')
                self.StatusText.Text = (
                    u'Could not refresh the standards database. '
                    u'Kodama will continue using the previous version. '
                    u'Details: {}'.format(err[:120])
                )
                self.StatusText.Foreground = self._RED
                # Keep title-bar X so user can dismiss after reading

        except Exception:
            pass

    def _start_auto_close_timer(self):
        """Start a 3-second countdown timer to auto-close the toast."""
        try:
            auto_timer = DispatcherTimer()
            auto_timer.Interval = TimeSpan.FromSeconds(3)

            def _auto_close(s, e):
                try:
                    auto_timer.Stop()
                    self.Close()
                except Exception:
                    pass

            auto_timer.Tick += _auto_close
            auto_timer.Start()
        except Exception:
            pass
