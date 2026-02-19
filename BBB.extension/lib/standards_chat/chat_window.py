# -*- coding: utf-8 -*-
"""
Chat Window Controller
Manages the WPF window, user interactions, and coordinates API calls
"""

import clr
import random
clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')
clr.AddReference('WindowsBase')
clr.AddReference('System.Xaml')

from System.Windows import Window
from System.Windows.Markup import XamlReader
from System.Windows.Controls import TextBlock, Border, ScrollViewer, StackPanel, Orientation, Image, Button
from System.Windows.Shapes import Ellipse
from System.Windows.Documents import Run, Hyperlink
from System.Windows.Media import Brushes, SolidColorBrush, Color
from System.Windows.Media.Imaging import BitmapImage
from System.Windows.Media.Animation import DoubleAnimation, RepeatBehavior
from System.Windows import Thickness, TextWrapping, HorizontalAlignment, Duration
from System.Threading import Thread, ThreadStart
from System.Windows.Threading import Dispatcher, DispatcherTimer
from System import TimeSpan, Uri
import System
import os
import sys
import time
import json

# Add lib path
script_dir = os.path.dirname(__file__)
lib_path = os.path.join(os.path.dirname(script_dir), 'lib')
if lib_path not in sys.path:
    sys.path.append(lib_path)

from pyrevit import forms
from standards_chat.notion_client import NotionClient
from standards_chat.anthropic_client import AnthropicClient
from standards_chat.config_manager import ConfigManager
from standards_chat.utils import extract_revit_context, safe_print, safe_str
from standards_chat.usage_logger import UsageLogger
from standards_chat.revit_actions import RevitActionExecutor, parse_action_from_response
from standards_chat.history_manager import HistoryManager

# Logger that writes to file only (no console output)
def debug_log(message):
    """Write debug message to log file"""
    try:
        import io
        from datetime import datetime
        log_dir = os.path.join(os.environ.get('APPDATA', ''), 'BBB', 'StandardsAssistant')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_path = os.path.join(log_dir, 'debug_log.txt')
        with io.open(log_path, 'a', encoding='utf-8') as f:
            f.write(u"{} - {}\n".format(datetime.now().isoformat(), message))
    except Exception:
        pass


class StandardsChatWindow(forms.WPFWindow):
    """Main chat window for Kodama"""
    
    def __init__(self):
        """Initialize the chat window"""
        # Load XAML via pyrevit forms (registers window with pyRevit's manager,
        # ensuring it is closed safely on the UI thread during reload)
        xaml_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'ui', 'chat_window.xaml'
        )
        forms.WPFWindow.__init__(self, xaml_path)
        
        # Get UI elements from the XAML content tree
        self.messages_panel = self.FindName('MessagesPanel')
        self.input_textbox = self.FindName('InputTextBox')
        self.send_button = self.FindName('SendButton')
        self.status_text = self.FindName('StatusText')
        self.loading_overlay = self.FindName('LoadingOverlay')
        self.loading_status_text = self.FindName('LoadingStatusText')
        self.message_scrollviewer = self.FindName('MessageScrollViewer')
        self.spinner_rotation = self.FindName('SpinnerRotation')
        self.header_icon = self.FindName('HeaderIcon')
        self.header_icon_button = self.FindName('HeaderIconButton')
        self.ScreenshotToggle = self.FindName('ScreenshotToggle')
        
        # Sidebar elements
        self.sidebar = self.FindName('Sidebar')
        self.sidebar_column = self.FindName('SidebarColumn')
        self.toggle_sidebar_button = self.FindName('ToggleSidebarButton')
        self.new_chat_button = self.FindName('NewChatButton')
        self.history_listbox = self.FindName('HistoryListBox')
        
        # Load icon image
        self._load_header_icon()

        # Cache bot icon bitmap for avatars
        self._bot_icon_bitmap = None
        try:
            # Check for overridden avatar in avatars folder first
            script_dir = os.path.dirname(__file__)
            lib_dir = os.path.dirname(script_dir)
            custom_bot_icon = os.path.join(lib_dir, 'ui', 'avatars', 'Kodama.png')
            
            if os.path.exists(custom_bot_icon):
                bmp = BitmapImage()
                bmp.BeginInit()
                bmp.UriSource = Uri("file:///" + custom_bot_icon.replace("\\", "/"))
                bmp.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad
                bmp.EndInit()
                self._bot_icon_bitmap = bmp
            else:
                # Fallback to extension icon
                extension_dir_init = os.path.dirname(lib_dir)
                bot_icon_path = os.path.join(
                    extension_dir_init, 'Chat.tab', 'Kodama.panel',
                    'Kodama.pushbutton', 'icon.png'
                )
                if os.path.exists(bot_icon_path):
                    bmp = BitmapImage()
                    bmp.BeginInit()
                    bmp.UriSource = Uri("file:///" + bot_icon_path.replace("\\", "/"))
                    bmp.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad
                    bmp.EndInit()
                    self._bot_icon_bitmap = bmp
        except:
            pass

        # Animation
        self.spin_animation = None
        self.typing_timer = None
        
        # Cute loading messages
        self.loading_messages = [
            "Digging through the standards vault...",
            "Consulting the BIM oracle...",
            "Summoning the Revit spirits...",
            "Checking under all the annotation layers...",
            "Asking the elders...",
            "Rifling through the file cabinet...",
            "Squinting at the fine print...",
            "Putting on reading glasses...",
            "Connecting brain cells...",
            "Warming up the neural networks...",
            "Doing some mental gymnastics...",
            "Caffeinating the algorithms...",
            "Firing up the search engines...",
            "Spinning up the knowledge wheels...",
            "Crunching the data...",
            "Indexing all the things...",
            "Pretending to think really hard...",
            "Buying time with this cute message...",
            "Looking very busy and important...",
            "This is taking longer than expected...",
            "Adding suspense for dramatic effect...",
            "Taking my sweet time...",
            "Running in circles (efficiently)..."
        ]
        self.current_message_index = 0
        
        # Initialize clients
        try:
            self.config = ConfigManager()
            
            # Initialize standards client based on config
            standards_source = self.config.get('features', 'standards_source', 'notion')
            if standards_source == 'sharepoint':
                from standards_chat.sharepoint_client import SharePointClient
                self.standards_client = SharePointClient(self.config)
            else:
                self.standards_client = NotionClient(self.config)
                
            self.anthropic = AnthropicClient(self.config)
            
            # Initialize vector DB client if enabled and user is in whitelist
            self.vector_db_client = None
            try:
                if self.config.get_config('features.enable_vector_search', False):
                    debug_log("Vector search is enabled, attempting to initialize client")
                    # 1. Try Native Client (CPython)
                    try:
                        # Use dynamic import to avoid IronPython parsing issues
                        vector_db_module = __import__('standards_chat.vector_db_client', fromlist=['VectorDBClient'])
                        VectorDBClient = vector_db_module.VectorDBClient
                        temp_vdb = VectorDBClient(self.config)
                        if temp_vdb.is_developer_mode_enabled():
                            self.vector_db_client = temp_vdb
                            debug_log("Using native VectorDBClient")
                        else:
                            debug_log("Developer mode not enabled, skipping native client")
                    except ImportError as ie:
                        debug_log("Native VectorDBClient import failed: {}".format(safe_str(ie)))
                        # 2. Native failed (IronPython or missing pkgs), try Interop Client
                        try:
                            # Use interop client to call CLI
                            interop_module = __import__('standards_chat.vector_db_interop', fromlist=['VectorDBInteropClient'])
                            VectorDBInteropClient = interop_module.VectorDBInteropClient
                            self.vector_db_client = VectorDBInteropClient(self.config)
                            debug_log("Using VectorDBInteropClient (CLI mode)")
                        except Exception as ex:
                            safe_print("Vector DB Interop failed: {}".format(safe_str(ex)))
                else:
                    debug_log("Vector search is disabled in config")
            except Exception as e:
                safe_print("Vector DB initialization error: {}".format(safe_str(e)))
            
            # Initialize usage logger
            central_log_dir = self.config.get('logging', 'central_log_dir')
            self.usage_logger = UsageLogger(
                central_log_dir=central_log_dir
            )
            
            # Initialize action executor
            try:
                from pyrevit import revit
                self.action_executor = RevitActionExecutor(revit.doc, revit.uidoc)
            except:
                self.action_executor = None
            
            # Initialize history manager
            self.history_manager = HistoryManager()
            
            # Load SharePoint index if available
            self.sharepoint_index = []
            try:
                index_path = os.path.join(self.config.config_dir, 'sharepoint_index.json')
                if os.path.exists(index_path):
                    f = None
                    try:
                        f = open(index_path, 'r')
                        self.sharepoint_index = json.load(f)
                    finally:
                        if f:
                            try:
                                f.close()
                            except:
                                pass
            except Exception as e:
                safe_print("Error loading SharePoint index: {}".format(safe_str(e)))
            
        except Exception as e:
            # Show error in status - use ASCII-safe conversion
            from standards_chat.utils import safe_str_ascii
            self.status_text.Text = "Configuration Error: {}".format(safe_str_ascii(e))
            self.send_button.IsEnabled = False
            return
        
        # Conversation history
        self.conversation = []
        
        # Session tracking
        self.current_session_id = None
        self.session_title = None
        
        # Track active action button
        self.active_action_button = None
        
        # Cancellation flag and reference for background query thread.
        # Set _cancel_requested = True in on_closed so the thread exits cleanly
        # before shared references are nulled.
        self._cancel_requested = False
        self._bg_thread = None
        
        # Wire up events
        self.send_button.Click += self.on_send_click
        self.input_textbox.KeyDown += self.on_input_keydown
        self.input_textbox.TextChanged += self.on_input_text_changed
        self.toggle_sidebar_button.Click += self.on_toggle_sidebar_click
        self.new_chat_button.Click += self.on_new_chat_click
        self.history_listbox.SelectionChanged += self.on_history_selection_changed
        if self.header_icon_button:
            self.header_icon_button.Click += self.on_header_icon_click
            
        # Cleanup on close
        self.Closed += self.on_closed
        
        # Load chat history into sidebar
        self.Loaded += self.on_window_loaded
        
        # Focus input box
        self.Loaded += lambda s, e: self.input_textbox.Focus()
    
    def on_closed(self, sender, args):
        """Handle cleanup when window closes"""
        try:
            # Signal the background query thread to stop BEFORE nulling shared
            # references so the thread doesn't hit a NullReferenceError mid-flight.
            self._cancel_requested = True
            if hasattr(self, '_bg_thread') and self._bg_thread is not None:
                try:
                    self._bg_thread.Join(500)  # brief wait; IsBackground ensures no hard block
                except Exception:
                    pass
                self._bg_thread = None
            
            # Stop any timers
            if hasattr(self, 'typing_timer') and self.typing_timer:
                try:
                    self.typing_timer.Stop()
                except Exception:
                    pass
                self.typing_timer = None
            
            # Clear references to help GC
            self.config = None
            self.standards_client = None
            self.anthropic = None
            self.vector_db_client = None
            self.usage_logger = None
            self.action_executor = None
            self.history_manager = None
            
            # Force garbage collection in IronPython
            import gc
            gc.collect()
        except Exception:
            # Swallow any errors during cleanup
            pass

    def on_header_icon_click(self, sender, args):
        """Open the standards website"""
        try:
            from System.Diagnostics import Process, ProcessStartInfo
            psi = ProcessStartInfo("https://beyerblinderbelle.sharepoint.com/sites/revitstandards")
            psi.UseShellExecute = True
            Process.Start(psi)
        except Exception as e:
            safe_print("Error opening URL: {}".format(safe_str(e)))
    
    def _load_header_icon(self):
        """Load the icon from the button folder into the header"""
        try:
            # Find the icon path - go up from lib/standards_chat to BBB.extension root
            script_dir = os.path.dirname(__file__)  # lib/standards_chat
            lib_dir = os.path.dirname(script_dir)  # lib
            
            # 1. Try Custom Kodama Avatar from avatars folder
            avatar_icon_path = os.path.join(lib_dir, 'ui', 'avatars', 'Kodama.png')
            
            final_icon_path = None
            if os.path.exists(avatar_icon_path):
                final_icon_path = avatar_icon_path
            else:
                # 2. Fallback to extension icon
                extension_dir = os.path.dirname(lib_dir)  # BBB.extension
                final_icon_path = os.path.join(
                    extension_dir,
                    'Chat.tab',
                    'Kodama.panel',
                    'Kodama.pushbutton',
                    'icon.png'
                )
            
            if final_icon_path and os.path.exists(final_icon_path):
                bitmap = BitmapImage()
                bitmap.BeginInit()
                bitmap.UriSource = Uri("file:///" + final_icon_path.replace("\\", "/"))
                bitmap.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad
                bitmap.EndInit()
                self.header_icon.Source = bitmap
            else:
                safe_print("Icon file not found at: {}".format(safe_str(final_icon_path)))
        except Exception as e:
            # Print error for debugging
            safe_print("Could not load header icon: {}".format(safe_str(e)))
    
    def _get_user_display_name(self):
        """Get user's display name for personalization"""
        # Try config first
        try:
            config_name = self.config.get('user', 'name', '')
            if config_name:
                return config_name
        except:
            pass

        # Fall back to Windows USERNAME environment variable
        username = os.environ.get('USERNAME', '')
        if username:
            # Reverted ctypes username retrieval due to instability in IronPython
            return username.capitalize()

        return ''

    def _open_settings(self, sender, args):
        """Open settings window"""
        try:
            from standards_chat.settings_window import SettingsWindow
            settings = SettingsWindow(self.config.config_dir)
            settings.ShowDialog()
            
            # Reload config to get new values
            self.config = ConfigManager()
        except Exception as e:
            safe_print("Error opening settings: {}".format(safe_str(e)))

    def _add_welcome_message(self):
        """Add a dynamic welcome message with suggested prompts"""
        import random
        from System.Windows.Markup import XamlReader
        # Removed InlineUIContainer as it causes crashes in some contexts
        # from System.Windows.Documents import InlineUIContainer 

        # Check if we are using a configured name or fallback
        config_name = None
        try:
            config_name = self.config.get('user', 'name', '')
        except:
            pass
            
        display_name = self._get_user_display_name()
        is_default_name = not config_name and display_name # True if using fallback and not manually set
        
        # Templates
        greetings = [
            "Hey{}, what can I help you with today?",
            "Hi{}, got a Revit question?",
            "Hello{}! Ask me anything about BBB's Revit standards.",
            "Hey{}! What are you working on today?",
            "Hi{}, ready to help with your Revit standards questions.",
        ]

        chosen_template = random.choice(greetings)
        parts = chosen_template.split('{}')
        prefix = parts[0]
        suffix = parts[1] if len(parts) > 1 else ""

        # Build the welcome bubble
        border = Border()
        border.Style = self.FindResource("MessageBubbleAssistant")
        border.Name = "WelcomeMessage"

        stack = StackPanel()

        tb = TextBlock()
        tb.TextWrapping = TextWrapping.Wrap
        tb.Foreground = self.FindResource("TextPrimaryColor")
        tb.LineHeight = 20

        # Add prefix
        prefix_run = Run(prefix)
        prefix_run.FontWeight = System.Windows.FontWeights.SemiBold
        tb.Inlines.Add(prefix_run)
        
        # Add formatted name
        if display_name:
            name_text = " " + display_name
            if is_default_name:
                link = Hyperlink()
                link.Click += self._open_settings
                link.ToolTip = "Click here to change how I address you"
                link.TextDecorations = System.Windows.TextDecorations.Underline
                link.Foreground = self.FindResource("TextPrimaryColor") 
                
                name_run = Run(name_text)
                name_run.FontWeight = System.Windows.FontWeights.SemiBold
                link.Inlines.Add(name_run)
                
                tb.Inlines.Add(link)
            else:
                name_run = Run(name_text)
                name_run.FontWeight = System.Windows.FontWeights.SemiBold
                tb.Inlines.Add(name_run)
        
        # Add suffix
        suffix_run = Run(suffix)
        suffix_run.FontWeight = System.Windows.FontWeights.SemiBold
        tb.Inlines.Add(suffix_run)

        stack.Children.Add(tb)

        # Add suggested prompt chips
        try:
            prompts = self.config.get('ui', 'suggested_prompts', [])
            if not prompts:
                prompts = [
                    "What are the naming conventions for views?",
                    "How should I set up worksets?",
                    "What are the standard line weights?"
                ]
            elif len(prompts) > 3:
                # Randomly select 3 prompts if we have more than 3
                prompts = random.sample(prompts, 3)
        except:
            prompts = [
                "What are the naming conventions for views?",
                "How should I set up worksets?",
                "What are the standard line weights?"
            ]

        if prompts:
            from System.Windows.Controls import WrapPanel
            prompts_panel = WrapPanel()
            prompts_panel.Margin = Thickness(0, 12, 0, 0)

            for prompt_text in prompts:
                try:
                    safe_text = prompt_text.replace('"', '&quot;').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    chip_xaml = '<Button xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" Content="{}" Padding="10,6" Margin="0,4,8,4" FontSize="11" FontFamily="Segoe UI" Cursor="Hand" Background="#F0F0F0" Foreground="#323130" BorderBrush="#E0E0E0" BorderThickness="1"><Button.Template><ControlTemplate TargetType="Button"><Border Background="{{TemplateBinding Background}}" BorderBrush="{{TemplateBinding BorderBrush}}" BorderThickness="{{TemplateBinding BorderThickness}}" CornerRadius="12" Padding="{{TemplateBinding Padding}}"><ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/></Border><ControlTemplate.Triggers><Trigger Property="IsMouseOver" Value="True"><Setter Property="Background" Value="#E1DFDD"/></Trigger></ControlTemplate.Triggers></ControlTemplate></Button.Template></Button>'.format(safe_text)
                    chip = XamlReader.Parse(chip_xaml)
                    chip.Tag = prompt_text
                    chip.Click += self._on_suggested_prompt_click
                    prompts_panel.Children.Add(chip)
                except Exception as e:
                    safe_print(u"Error creating prompt chip: {}".format(safe_str(e)))

            stack.Children.Add(prompts_panel)

        border.Child = stack

        # Wrap with bot avatar
        container = self._wrap_with_avatar(border, is_user=False)
        self.messages_panel.Children.Insert(0, container)

    def _on_suggested_prompt_click(self, sender, args):
        """Handle suggested prompt chip click"""
        prompt_text = sender.Tag
        if prompt_text:
            # Hide the suggestions panel (parent of the button)
            try:
                from System.Windows import Visibility
                if sender.Parent:
                    sender.Parent.Visibility = Visibility.Collapsed
            except:
                pass
                
            self.input_textbox.Text = prompt_text
            self.send_message()

    def _create_bot_avatar(self):
        """Create a small Kodama bot avatar element"""
        avatar_border = Border()
        avatar_border.Width = 32
        avatar_border.Height = 32
        avatar_border.CornerRadius = System.Windows.CornerRadius(16)
        avatar_border.Background = SolidColorBrush(Color.FromRgb(215, 235, 255)) # slightly stronger blue
        avatar_border.VerticalAlignment = System.Windows.VerticalAlignment.Top
        avatar_border.Margin = Thickness(0, 5, 8, 0)

        if self._bot_icon_bitmap:
            from System.Windows.Media import ImageBrush, Stretch
            brush = ImageBrush(self._bot_icon_bitmap)
            brush.Stretch = Stretch.UniformToFill
            avatar_border.Background = brush
        
        return avatar_border

    def _create_user_avatar(self):
        """Create a user avatar element"""
        avatar_border = Border()
        avatar_border.Width = 32
        avatar_border.Height = 32
        avatar_border.CornerRadius = System.Windows.CornerRadius(16)
        avatar_border.Background = SolidColorBrush(Color.FromRgb(0x00, 0x78, 0xD4))
        avatar_border.VerticalAlignment = System.Windows.VerticalAlignment.Top
        avatar_border.Margin = Thickness(8, 5, 0, 0)

        # Enable interaction
        avatar_border.ToolTip = "Change my Avatar"
        try:
            avatar_border.Cursor = System.Windows.Input.Cursors.Hand
        except:
            # Fallback if cursor access fails
            pass
        avatar_border.MouseLeftButtonUp += self._open_settings

        # Check for configured avatar
        avatar_file = self.config.get('user', 'avatar', None)
        if avatar_file:
            try:
                # Need to construct path to avatars folder
                # We can't use __file__ reliably in all contexts, but assuming standard structure
                import os
                
                # Try to find lib/ui/avatars
                # Chat window is in lib/standards_chat
                # So we go up two levels to lib, then down to ui/avatars
                
                # Use current directory of module if possible
                module_dir = os.path.dirname(os.path.abspath(__file__)) 
                lib_dir = os.path.dirname(module_dir)
                avatar_path = os.path.join(lib_dir, 'ui', 'avatars', avatar_file)
                
                if os.path.exists(avatar_path):
                    bitmap = BitmapImage()
                    bitmap.BeginInit()
                    bitmap.UriSource = Uri("file:///" + avatar_path.replace("\\", "/"))
                    bitmap.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad
                    bitmap.EndInit()
                    
                    from System.Windows.Media import ImageBrush, Stretch
                    brush = ImageBrush(bitmap)
                    brush.Stretch = Stretch.UniformToFill
                    avatar_border.Background = brush
                    return avatar_border
            except Exception as e:
                # Fallback to initials if image load fails
                safe_print("Error loading avatar: " + safe_str(e))
                pass

        name = self._get_user_display_name()
        initial = name[0].upper() if name else "U"

        initials_text = TextBlock()
        initials_text.Text = initial
        initials_text.FontSize = 14 # Increased from 11
        initials_text.FontWeight = System.Windows.FontWeights.SemiBold
        initials_text.Foreground = Brushes.White
        initials_text.HorizontalAlignment = HorizontalAlignment.Center
        initials_text.VerticalAlignment = System.Windows.VerticalAlignment.Center

        avatar_border.Child = initials_text
        return avatar_border

    def _wrap_with_avatar(self, bubble, is_user):
        """Wrap a message bubble in a Grid with an avatar"""
        from System.Windows.Controls import Grid, ColumnDefinition, StackPanel
        from System.Windows import GridLength, GridUnitType

        container = Grid()
        container.Margin = Thickness(0, 2, 0, 2)

        if is_user:
            # User: [flex space] [bubble] [avatar]
            col1 = ColumnDefinition()
            col1.Width = GridLength(1, GridUnitType.Star)
            col2 = ColumnDefinition()
            col2.Width = GridLength.Auto
            col3 = ColumnDefinition()
            col3.Width = GridLength.Auto
            container.ColumnDefinitions.Add(col1)
            container.ColumnDefinitions.Add(col2)
            container.ColumnDefinitions.Add(col3)

            avatar = self._create_user_avatar()
            Grid.SetColumn(bubble, 1)
            Grid.SetColumn(avatar, 2)
            container.Children.Add(bubble)
            container.Children.Add(avatar)
        else:
            # Assistant: [avatar] [bubble_stack]
            # We use a stack here to allow appending the sources panel easily below the bubble
            # while keeping alignment with the avatar
            
            col1 = ColumnDefinition()
            col1.Width = GridLength.Auto
            col2 = ColumnDefinition()
            col2.Width = GridLength(1, GridUnitType.Star) # Take remaining space to allow wrapping
            container.ColumnDefinitions.Add(col1)
            container.ColumnDefinitions.Add(col2)

            avatar = self._create_bot_avatar()
            Grid.SetColumn(avatar, 0)
            
            # Create a stack for the bubble + potential sources
            bubble_stack = StackPanel()
            if hasattr(bubble, 'HorizontalAlignment'):
                bubble.HorizontalAlignment = HorizontalAlignment.Left
                
            bubble_stack.Children.Add(bubble)
            
            # If we are in add_message and sources were provided (i.e. loading from history)
            # We need to render them here. 
            # Note: add_message calls this method. But this method doesn't take sources.
            # We can rely on add_message to modify this stack if needed, OR
            # Just return the container and let caller add to children?
            # But the caller (add_message) adds 'bubble' as child. 'bubble' is now child of 'bubble_stack'.
            # This logic change requires update in add_message too?
            # No, 'bubble' passed in IS the bubble border.
            
            Grid.SetColumn(bubble_stack, 1)
            container.Children.Add(avatar)
            container.Children.Add(bubble_stack)

        return container

    def _create_sources_panel(self, sources):
        """Create a separate panel for sources (displayed below bubble as footnotes)"""
        if not sources:
            return None
            
        from System.Windows.Controls import StackPanel, Image
        from System.Windows.Documents import Run, Hyperlink, InlineUIContainer
        from System.Windows.Media.Imaging import BitmapImage
        
        # Try to load SharePoint icon
        sp_icon_bitmap = None
        pdf_icon_bitmap = None
        video_icon_bitmap = None
        try:
            script_dir = os.path.dirname(__file__)
            lib_dir = os.path.dirname(script_dir)
            
            # Load SharePoint icon
            sp_icon_path = os.path.join(lib_dir, 'ui', 'sharepoint_icon.png')
            if os.path.exists(sp_icon_path):
                sp_icon_bitmap = BitmapImage()
                sp_icon_bitmap.BeginInit()
                sp_icon_bitmap.UriSource = Uri("file:///" + sp_icon_path.replace("\\", "/"))
                sp_icon_bitmap.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad
                sp_icon_bitmap.EndInit()
            
            # Load PDF icon
            pdf_icon_path = os.path.join(lib_dir, 'ui', 'pdf_icon.png')
            if os.path.exists(pdf_icon_path):
                pdf_icon_bitmap = BitmapImage()
                pdf_icon_bitmap.BeginInit()
                pdf_icon_bitmap.UriSource = Uri("file:///" + pdf_icon_path.replace("\\", "/"))
                pdf_icon_bitmap.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad
                pdf_icon_bitmap.EndInit()
            
            # Load video icon
            video_icon_path = os.path.join(lib_dir, 'ui', 'video_icon.png')
            if os.path.exists(video_icon_path):
                video_icon_bitmap = BitmapImage()
                video_icon_bitmap.BeginInit()
                video_icon_bitmap.UriSource = Uri("file:///" + video_icon_path.replace("\\", "/"))
                video_icon_bitmap.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad
                video_icon_bitmap.EndInit()
        except:
            pass
        
        panel = StackPanel() 
        panel.Orientation = Orientation.Vertical
        panel.Margin = Thickness(12, 8, 12, 8) 
        
        # Divider line
        divider = Border()
        divider.Height = 1
        divider.Background = SolidColorBrush(Color.FromRgb(0xE0, 0xE0, 0xE0))
        divider.Margin = Thickness(0, 0, 0, 8)
        divider.HorizontalAlignment = HorizontalAlignment.Left
        divider.Width = 200
        panel.Children.Add(divider)
        
        grey_brush = SolidColorBrush(Color.FromRgb(0x60, 0x5E, 0x5C))

        for i, source in enumerate(sources, 1):
            # Create footnote item: "[1] Title"
            tb = TextBlock()
            tb.FontSize = 11
            tb.Margin = Thickness(0, 2, 0, 2)
            tb.TextWrapping = TextWrapping.Wrap
            
            # Number [n]
            num_run = Run("[{}] ".format(i))
            num_run.Foreground = grey_brush
            # num_run.BaselineAlignment = System.Windows.BaselineAlignment.Superscript
            # Superscript often messes up line height in WPF TextBlock, keeping inline for now
            tb.Inlines.Add(num_run)
            
            # Clean Title
            title = source.get('title', 'Unknown Source')
            # Remove "Sharepoint Page" if present at end
            if title.lower().endswith(" - sharepoint page"):
                title = title[:-17] # len(" - sharepoint page")
            elif title.lower().endswith(" sharepoint page"):
                title = title[:-16]

            # Clickable Title
            link = Hyperlink()
            link.TextDecorations = None
            link.Foreground = self.FindResource("PrimaryColor")
            link.NavigateUri = System.Uri(source['url'])
            link.RequestNavigate += self.on_hyperlink_click
            
            link_run = Run(title)
            link.Inlines.Add(link_run)
            
            # Tooltip with full details
            link.ToolTip = source.get('title', title)
            
            tb.Inlines.Add(link)
            
            # Select appropriate icon based on category
            category = source.get('category', '')
            icon_bitmap = None
            if 'PDF' in category:
                icon_bitmap = pdf_icon_bitmap
            elif 'Training Video' in category or 'Video' in category:
                icon_bitmap = video_icon_bitmap
            else:
                icon_bitmap = sp_icon_bitmap
            
            # Add icon if available
            if icon_bitmap:
                img = Image()
                img.Source = icon_bitmap
                img.Width = 10
                img.Height = 10
                # img.Margin = Thickness(4, 0, 0, 0)
                container = InlineUIContainer(img)
                container.BaselineAlignment = System.Windows.BaselineAlignment.Center
                
                # Add a space before icon
                tb.Inlines.Add(Run(" "))
                tb.Inlines.Add(container)
            
            panel.Children.Add(tb)
            
        return panel

    def _add_sources_to_textblock(self, textblock, sources):
        """Add subdued source links to a textblock"""
        if not sources:
            return

        # Simple spacing (no divider, no header)
        textblock.Inlines.Add(Run("\n\n"))

        grey_brush = SolidColorBrush(Color.FromRgb(0x60, 0x5E, 0x5C))

        # Try to load SharePoint icon
        sp_icon_bitmap = None
        try:
            script_dir = os.path.dirname(__file__)
            lib_dir = os.path.dirname(script_dir)
            sp_icon_path = os.path.join(lib_dir, 'ui', 'sharepoint_icon.png')
            if os.path.exists(sp_icon_path):
                sp_icon_bitmap = BitmapImage()
                sp_icon_bitmap.BeginInit()
                sp_icon_bitmap.UriSource = Uri("file:///" + sp_icon_path.replace("\\", "/"))
                sp_icon_bitmap.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad
                sp_icon_bitmap.EndInit()
        except:
            pass

        for source in sources:
            textblock.Inlines.Add(Run("\n"))

            # Create hyperlink in grey, smaller font
            hyperlink = Hyperlink()
            link_run = Run(source['title'])
            link_run.FontSize = 10
            hyperlink.Inlines.Add(link_run)
            hyperlink.NavigateUri = System.Uri(source['url'])
            hyperlink.RequestNavigate += self.on_hyperlink_click
            hyperlink.Foreground = grey_brush
            hyperlink.TextDecorations = None

            textblock.Inlines.Add(hyperlink)

            # Add SharePoint icon or fallback
            if sp_icon_bitmap:
                img = Image()
                img.Source = sp_icon_bitmap
                img.Width = 12
                img.Height = 12
                img.Margin = Thickness(4, 0, 0, 0)
                from System.Windows.Documents import InlineUIContainer
                container = InlineUIContainer(img)
                container.BaselineAlignment = System.Windows.BaselineAlignment.Center
                textblock.Inlines.Add(container)

            # Add category if available
            if source.get('category'):
                category_text = Run("  {}".format(source['category']))
                category_text.FontSize = 9
                category_text.Foreground = grey_brush
                textblock.Inlines.Add(category_text)

    def on_send_click(self, sender, args):
        """Handle send button click"""
        self.send_message()
    
    def on_input_keydown(self, sender, args):
        """Handle keyboard input (Enter to send or activate action button, Shift+Enter for new line)"""
        if args.Key == System.Windows.Input.Key.Enter:
            # If Shift is held, allow new line (don't send)
            if System.Windows.Input.Keyboard.Modifiers != \
               System.Windows.Input.ModifierKeys.Shift:
                # If there's an active action button, click it instead of sending
                if self.active_action_button and self.active_action_button.IsEnabled:
                    self.active_action_button.RaiseEvent(
                        System.Windows.RoutedEventArgs(Button.ClickEvent)
                    )
                else:
                    self.send_message()
                args.Handled = True
    
    def on_input_text_changed(self, sender, args):
        """Enable/disable send button based on input text"""
        has_text = len(self.input_textbox.Text.strip()) > 0
        self.send_button.IsEnabled = has_text

    def on_window_loaded(self, sender, args):
        """Handle window loaded event - populate history list and welcome"""
        self.refresh_history_list()

        # Add dynamic welcome message
        self._add_welcome_message()

        # Auto-open sidebar if user has more than 3 chat sessions
        from System.Windows import GridLength, GridUnitType
        sessions = self.history_manager.list_sessions()
        if len(sessions) > 3:
            self.sidebar_column.Width = GridLength(250, GridUnitType.Pixel)
    
    def on_toggle_sidebar_click(self, sender, args):
        """Toggle sidebar visibility"""
        from System.Windows import GridLength, GridUnitType
        
        # Simple toggle for now (animation requires more complex setup with Storyboards in code-behind)
        if self.sidebar_column.Width.Value > 0:
            # Hide sidebar
            self.sidebar_column.Width = GridLength(0, GridUnitType.Pixel)
            # Icon remains the history clock
        else:
            # Show sidebar
            self.sidebar_column.Width = GridLength(250, GridUnitType.Pixel)
            
    def on_delete_history_item(self, sender, args):
        """Handle delete button click in history list"""
        try:
            button = sender
            session_id = button.Tag
            
            if not session_id:
                return
                
            # Delete from disk
            if self.history_manager.delete_session(session_id):
                # If it's the current session, clear the chat
                if session_id == self.current_session_id:
                    self.on_new_chat_click(None, None)
                
                # Refresh list
                self.refresh_history_list()
                
        except Exception as e:
            safe_print("Error deleting session: {}".format(safe_str(e)))
    
    def on_new_chat_click(self, sender, args):
        """Start a new chat session"""
        from System.Windows import GridLength, GridUnitType

        # Collapse sidebar
        self.sidebar_column.Width = GridLength(0, GridUnitType.Pixel)

        # If current conversation has content, save it first
        if self.conversation:
            self.save_current_session()

        # Clear current conversation
        self.conversation = []
        self.current_session_id = None
        self.session_title = None

        # Clear all messages and add fresh welcome with new random greeting
        self.messages_panel.Children.Clear()
        self._add_welcome_message()

        # Clear input
        self.input_textbox.Clear()
        self.input_textbox.Focus()

        # Refresh history list
        self.refresh_history_list()
    
    def on_history_selection_changed(self, sender, args):
        """Handle history list selection change"""
        if self.history_listbox.SelectedItem is None:
            return
        
        # In WPF ListBox, SelectedItem is the content we added (ListBoxItem)
        # We stored the session_id in the Tag property
        selected_item = self.history_listbox.SelectedItem
        
        # Check if it has a Tag property (it should be a ListBoxItem)
        if hasattr(selected_item, 'Tag'):
            session_id = selected_item.Tag
        else:
            # Fallback if something else was selected
            return
            
        # Don't reload if it's the current session
        if session_id == self.current_session_id:
            return
            
        # Collapse sidebar
        from System.Windows import GridLength, GridUnitType
        self.sidebar_column.Width = GridLength(0, GridUnitType.Pixel)
        
        # Save current session if it has content
        if self.conversation:
            self.save_current_session()
        
        # Load selected session
        self.load_chat_session(session_id)
    
    def refresh_history_list(self):
        """Refresh the history list from disk"""
        from System.Windows.Controls import ListBoxItem, Grid, ColumnDefinition, StackPanel, TextBlock, Button, ControlTemplate, ContentPresenter, Border
        from System.Windows import GridLength, GridUnitType, Thickness, TextTrimming, TextWrapping
        from System.Windows.Media import Brushes, SolidColorBrush, Color
        
        sessions = self.history_manager.list_sessions()
        
        # Clear current items
        self.history_listbox.Items.Clear()
        
        # Add sessions to list
        for session in sessions:
            # Create ListBoxItem
            item = ListBoxItem()
            item.Tag = session['session_id']
            
            # Create Grid
            grid = Grid()
            grid.Margin = Thickness(0, 0, 0, 0) # Compact margin handled by ItemStyle
            col1 = ColumnDefinition()
            col1.Width = GridLength(1, GridUnitType.Star)
            col2 = ColumnDefinition()
            col2.Width = GridLength.Auto
            grid.ColumnDefinitions.Add(col1)
            grid.ColumnDefinitions.Add(col2)
            
            # Text Stack
            stack = StackPanel()
            Grid.SetColumn(stack, 0)
            
            title_txt = TextBlock()
            title_txt.Text = session['title']
            title_txt.FontSize = 12
            title_txt.TextWrapping = TextWrapping.Wrap
            title_txt.TextTrimming = TextTrimming.CharacterEllipsis
            title_txt.MaxHeight = 50 # Allow ~3 lines
            title_txt.Foreground = self.FindResource("TextPrimaryColor")
            title_txt.ToolTip = session['title']

            stack.Children.Add(title_txt)
            
            # Delete Button
            del_btn = Button()
            del_btn.Content = "×"
            del_btn.Width = 20
            del_btn.Height = 20
            del_btn.Margin = Thickness(5, 0, 0, 0)
            del_btn.Background = Brushes.Transparent
            del_btn.Foreground = self.FindResource("TextSecondaryColor")
            del_btn.BorderThickness = Thickness(0)
            del_btn.FontSize = 14
            del_btn.FontWeight = System.Windows.FontWeights.Bold
            del_btn.Cursor = System.Windows.Input.Cursors.Hand
            del_btn.Tag = session['session_id']
            del_btn.ToolTip = "Delete Chat"
            del_btn.VerticalAlignment = System.Windows.VerticalAlignment.Top # Align to top for multiline
            del_btn.Style = self.FindResource("SidebarButtonStyle") # Use sidebar style
            Grid.SetColumn(del_btn, 1)
            
            # Wire up delete event
            del_btn.Click += self.on_delete_history_item
            
            grid.Children.Add(stack)
            grid.Children.Add(del_btn)
            
            item.Content = grid
            self.history_listbox.Items.Add(item)
    
    def save_current_session(self):
        """Save the current chat session"""
        if not self.conversation:
            return
        
        # Create new session ID if we don't have one
        if not self.current_session_id:
            self.current_session_id = self.history_manager.create_new_session()
        
        # Use existing title or create from first message
        if not self.session_title:
            self.session_title = self.conversation[0].get('user', 'Untitled Chat')
        
        # Save to disk
        self.history_manager.save_session(
            self.current_session_id,
            self.conversation,
            self.session_title
        )
    
    def load_chat_session(self, session_id):
        """Load a chat session from disk"""
        session_data = self.history_manager.load_session(session_id)

        if not session_data:
            return

        # Set current session
        self.current_session_id = session_id
        self.session_title = session_data.get('title', 'Untitled Chat')
        self.conversation = session_data.get('conversation', [])

        # Clear all messages and re-add welcome
        self.messages_panel.Children.Clear()
        self._add_welcome_message()

        # Show session date as subtle centered text
        timestamp = session_data.get('timestamp', '')
        if timestamp:
            try:
                from datetime import datetime
                if '.' in timestamp:
                    dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f")
                else:
                    dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S")
                date_str = dt.strftime('%B %d, %Y')
            except:
                date_str = timestamp

            date_label = TextBlock()
            date_label.Text = date_str
            date_label.FontSize = 10
            date_label.Foreground = self.FindResource("TextSecondaryColor")
            date_label.HorizontalAlignment = HorizontalAlignment.Center
            date_label.Margin = Thickness(0, 5, 0, 10)
            self.messages_panel.Children.Add(date_label)

        # Re-render all messages
        for exchange in self.conversation:
            self.add_message(exchange['user'], is_user=True)
            self.add_message(
                exchange['assistant'],
                is_user=False,
                sources=exchange.get('sources')
            )

        # Scroll to bottom
        self.message_scrollviewer.ScrollToBottom()

        # Focus input
        self.input_textbox.Focus()
    
    def send_message(self):
        """Send user message and get response"""
        user_input = self.input_textbox.Text.strip()
        
        if not user_input:
            return
        
        # Ensure we have a session id for the very first message so
        # the usage logger doesn't write the initial entry to a
        # file with session_id 'None'. Create a new session if needed.
        if not self.current_session_id:
            try:
                self.current_session_id = self.history_manager.create_new_session()
            except Exception:
                # Fallback: leave as None (usage_logger will handle), but this should not happen
                pass
        
        # Clear active action button when starting new query
        self.active_action_button = None
        
        # Track query start time for logging
        query_start_time = time.time()
        
        # Extract Revit context BEFORE starting background thread (must be on STA thread)
        # Only if enabled in settings
        revit_context = None
        if self.config.get('features', 'include_context', default=True):
            try:
                raw_context = extract_revit_context()
                if raw_context:
                    # Sanitize via JSON roundtrip to ensure no COM objects leak to background thread
                    # This also ensures deep copy
                    json_str = json.dumps(raw_context, ensure_ascii=False)
                    revit_context = json.loads(json_str)
            except Exception as e:
                safe_print("Warning: Failed to capture or sanitize Revit context: {}".format(safe_str(e)))
                revit_context = None
        
        # Capture screenshot if enabled via toggle
        from .utils import capture_revit_screenshot
        screenshot_base64 = None
        
        # Check toggle state
        include_screenshot = False
        if hasattr(self, 'ScreenshotToggle'):
            include_screenshot = self.ScreenshotToggle.IsChecked == True
            
            # Reset toggle after capturing intent
            if include_screenshot:
                self.ScreenshotToggle.IsChecked = False
        else:
            # Fallback to config
            include_screenshot = self.config.get('features', 'include_screenshot', default=True)
            
        if include_screenshot:
            # Hide window briefly to capture clean screenshot of Revit
            self.Hide()
            # Allow UI to update
            System.Windows.Forms.Application.DoEvents()
            time.sleep(0.2)
            
            try:
                screenshot_base64 = capture_revit_screenshot()
            finally:
                # Ensure window comes back
                self.Show()
                self.Activate()
        
        # Clear input
        self.input_textbox.Clear()
        
        # Add user message to UI
        self.add_message(user_input, is_user=True)
        
        # Add typing indicator
        self.add_typing_indicator()
        
        # Disable input while processing
        self.send_button.IsEnabled = False
        self.input_textbox.IsEnabled = False
        
        # Process in background thread
        def process_query():
            try:
                debug_log("process_query started")
                if getattr(self, '_cancel_requested', False):
                    return
                # Use direct user input for search - vector search handles semantics natively
                search_query = user_input
                keyword_tokens_in = 0
                keyword_tokens_out = 0
                
                # Search standards - use vector search if available
                debug_log("Calling search with query: {}".format(safe_str(user_input)))
                if self.vector_db_client is not None:
                    debug_log("Using vector_db_client for search")
                    # Use hybrid vector search (semantic + keyword)
                    relevant_pages = self.vector_db_client.hybrid_search(
                        query=user_input,  # Use original user input for semantic search
                        deduplicate=True
                    )
                    debug_log("Vector search returned {} pages".format(len(relevant_pages)))
                    if relevant_pages:
                        debug_log("First result: title='{}', score={:.4f}".format(
                            safe_str(relevant_pages[0].get('title', 'NO TITLE'))[:60],
                            float(relevant_pages[0].get('score', 0))
                        ))
                else:
                    debug_log("vector_db_client is None, using standards_client")
                    # Fall back to standard SharePoint keyword search
                    relevant_pages = self.standards_client.search_standards(search_query)
                    debug_log("search_standards returned {} pages".format(len(relevant_pages)))
                
                # Determine if search results are too low-confidence to answer the question.
                # A top score below 0.4 means the best match is a weak semantic overlap --
                # Claude will almost certainly not have a useful answer.
                LOW_CONFIDENCE_THRESHOLD = 0.4
                top_score = float(relevant_pages[0].get('score', 0)) if relevant_pages else 0.0
                self._show_dct_button = (top_score < LOW_CONFIDENCE_THRESHOLD)
                debug_log("top search score={:.4f}, show_dct_button={}".format(top_score, self._show_dct_button))
                
                # Remove typing indicator and add empty message bubble for streaming
                try:
                    self.Dispatcher.Invoke(self.start_streaming_response)
                    debug_log("start_streaming_response invoked")
                except Exception as start_err:
                    import traceback
                    safe_print("ERROR: Failed to invoke start_streaming_response: {}".format(safe_str(start_err)))
                    debug_log("ERROR invoking start_streaming_response: {}\n{}".format(
                        safe_str(start_err), traceback.format_exc()
                    ))
                
                debug_log("Calling Claude with {} pages".format(len(relevant_pages)))
                
                # Callback for streaming chunks
                def on_chunk(text_chunk):
                    try:
                        # Capture text_chunk value in closure to avoid lambda capture issues
                        chunk_to_append = text_chunk
                        try:
                            self.Dispatcher.Invoke(
                                lambda: self.append_to_streaming_response(chunk_to_append)
                            )
                        except Exception as disp_err:
                            safe_print("ERROR: Dispatcher.Invoke failed: {}".format(safe_str(disp_err)))
                            debug_log("ERROR: Dispatcher.Invoke failed: {}".format(safe_str(disp_err)))
                    except Exception as e:
                        safe_print(u"ERROR in on_chunk callback: {}".format(safe_str(e)))
                        debug_log(u"ERROR in on_chunk callback: {}".format(safe_str(e)))
                
                # Get streaming response from Claude
                if getattr(self, '_cancel_requested', False):
                    return
                response = self.anthropic.get_response_stream(
                    user_query=user_input,
                    notion_pages=relevant_pages,
                    revit_context=revit_context,
                    conversation_history=self.conversation,
                    callback=on_chunk,
                    screenshot_base64=screenshot_base64
                )
                
                debug_log("Claude response received, text length: {}".format(len(response.get('text', ''))))

                # Extract URLs from sources
                source_urls = []
                sources = response.get('sources', [])
                if sources:
                    for s in sources:
                        # Handle dictionary (most likely format)
                        if isinstance(s, dict):
                            url = s.get('url') or s.get('source')
                            if url: source_urls.append(url)
                        # Handle object with metadata
                        elif hasattr(s, 'metadata'):
                            url = s.metadata.get('source') or s.metadata.get('url')
                            if url: source_urls.append(url)
                        elif isinstance(s, str):
                            source_urls.append(s)

                # Extract token counts and model
                # Add tokens from keyword extraction step
                input_tokens = response.get('input_tokens', 0) + keyword_tokens_in
                output_tokens = response.get('output_tokens', 0) + keyword_tokens_out
                ai_model = response.get('model', 'unknown')

                # Calculate duration and log interaction
                duration_seconds = time.time() - query_start_time
                try:
                    if not getattr(self, '_cancel_requested', False) and self.usage_logger:
                        self.usage_logger.log_interaction(
                            query=user_input,
                            response_preview=response.get('text', ''),
                            source_count=len(response.get('sources', [])),
                            duration_seconds=duration_seconds,
                            revit_context=revit_context,
                            session_id=self.current_session_id,
                            screenshot_base64=screenshot_base64,
                            source_urls=source_urls,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            ai_model=ai_model
                        )
                except Exception as log_error:
                    # print("Error logging interaction: {}".format(str(log_error)))
                    pass
                
                if getattr(self, '_cancel_requested', False):
                    return
                
                # Update conversation history
                self.conversation.append({
                    'user': user_input,
                    'assistant': response['text'],
                    'sources': response['sources']
                })
                
                # Generate title if it's the first exchange or title is default
                if len(self.conversation) == 1 or self.session_title == "Untitled Chat":
                    try:
                        new_title = self.anthropic.generate_title(user_input, response['text'])
                        if new_title:
                            self.session_title = new_title
                    except Exception as e:
                        safe_print("Title generation failed: " + safe_str(e))
                
                # Auto-save session after each exchange
                self.save_current_session()
                
                # Refresh history list to show updated session
                self.Dispatcher.Invoke(self.refresh_history_list)
                
                # Add sources to the message
                self.Dispatcher.Invoke(
                    lambda: self.finish_streaming_response(response['sources'])
                )
                
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                safe_print("Error processing query: " + safe_str(e))
                safe_print(tb)

                # Write traceback to log file for debugging
                # Each write is independent so partial failures don't lose earlier lines
                try:
                    import os, io as _io
                    from datetime import datetime
                    from standards_chat.utils import safe_str_ascii, ascii_safe
                    log_dir = os.path.join(os.environ.get('APPDATA', ''), 'BBB', 'StandardsAssistant')
                    if not os.path.exists(log_dir):
                        os.makedirs(log_dir)
                    log_path = os.path.join(log_dir, 'error_log.txt')
                    f = _io.open(log_path, 'a', encoding='utf-8')
                    try:
                        f.write(u"\n=== {} ===\n".format(datetime.now().isoformat()))
                    except Exception:
                        pass
                    try:
                        f.write(u"Error type: {}\n".format(type(e).__name__))
                    except Exception:
                        pass
                    try:
                        # Use repr() which is safest for exception objects
                        f.write(u"Error repr: {}\n".format(ascii_safe(repr(e))))
                    except Exception:
                        pass
                    try:
                        f.write(u"Traceback:\n{}\n".format(ascii_safe(tb)))
                    except Exception:
                        pass
                    f.close()
                except Exception:
                    pass

                # Show simpler error to user but invalid COM object specifically
                # Ultra-safe error message creation - never let Unicode through
                try:
                    from standards_chat.utils import safe_str_ascii
                    err_text = safe_str_ascii(e)
                    if "COM object" in err_text and "RCW" in err_text:
                        err_text += "\n(Revit API context lost during background processing)"
                    # Double-check it's ASCII-safe before formatting
                    err_text = safe_str_ascii(err_text)
                except Exception as conv_err:
                    err_text = u"An error occurred (details in console)"

                # Show friendly fallback message with DCT ticket button instead of
                # exposing raw Python error details to the user.
                def show_error_response():
                    try:
                        # Start the streaming bubble if it was never opened
                        # (error occurred before start_streaming_response was called)
                        if not getattr(self, 'streaming_border', None):
                            self.start_streaming_response()
                        friendly_text = u"Sorry, something went wrong while processing your request."
                        self.streaming_text = friendly_text
                        if hasattr(self, 'streaming_textblock') and self.streaming_textblock:
                            self.streaming_textblock.Inlines.Clear()
                            self._add_formatted_text(self.streaming_textblock, friendly_text)
                        # Force the DCT ticket button to appear
                        self._show_dct_button = True
                        self.finish_streaming_response([])
                    except Exception as display_err:
                        safe_print(u"Error showing friendly error response: {}".format(safe_str(display_err)))
                        # Last-resort plain fallback if streaming path itself fails
                        try:
                            self.replace_typing_with_response(
                                u"Sorry, something went wrong. Please try again or open a ticket with DCT.",
                                None
                            )
                        except Exception:
                            pass

                self.Dispatcher.Invoke(show_error_response)
            
            finally:
                # Re-enable input
                self.Dispatcher.Invoke(self.enable_input)
        
        # Start background thread
        self._cancel_requested = False  # reset for this new query
        thread = Thread(ThreadStart(process_query))
        thread.SetApartmentState(System.Threading.ApartmentState.STA)
        thread.IsBackground = True
        self._bg_thread = thread
        thread.Start()
    
    def rotate_loading_message(self, sender, e):
        """Rotates through cute loading messages"""
        if hasattr(self, 'typing_status_text') and self.typing_status_text:
            message = random.choice(self.loading_messages)
            self.typing_status_text.Text = message

    def add_typing_indicator(self):
        """Add animated typing indicator bubble with status text on same line"""
        # Create border (message bubble)
        border = Border()
        border.Style = self.FindResource("MessageBubbleAssistant")

        # Single horizontal stack for dots + status text on same line
        dots_stack = StackPanel()
        dots_stack.Orientation = Orientation.Horizontal
        dots_stack.HorizontalAlignment = HorizontalAlignment.Left

        # Create three animated dots
        for i in range(3):
            dot = Ellipse()
            dot.Width = 8
            dot.Height = 8
            dot.Fill = self.FindResource("TextSecondaryColor")
            dot.Margin = Thickness(0 if i == 0 else 4, 0, 0, 0)
            dot.VerticalAlignment = System.Windows.VerticalAlignment.Center

            # Animate opacity
            animation = DoubleAnimation()
            animation.From = 0.3
            animation.To = 1.0
            animation.Duration = Duration(TimeSpan.FromSeconds(0.6))
            animation.AutoReverse = True
            animation.RepeatBehavior = RepeatBehavior.Forever
            animation.BeginTime = TimeSpan.FromSeconds(i * 0.2)

            dot.BeginAnimation(
                Ellipse.OpacityProperty,
                animation
            )

            dots_stack.Children.Add(dot)

        # Status text on same line as dots
        status_text = TextBlock()
        status_text.Text = random.choice(self.loading_messages)
        status_text.FontSize = 11
        status_text.Foreground = self.FindResource("TextSecondaryColor")
        status_text.Margin = Thickness(8, 0, 0, 0)
        status_text.VerticalAlignment = System.Windows.VerticalAlignment.Center
        status_text.Name = "TypingStatusText"

        # Animate status text opacity (subtle pulse)
        status_animation = DoubleAnimation()
        status_animation.From = 0.5
        status_animation.To = 1.0
        status_animation.Duration = Duration(TimeSpan.FromSeconds(1.5))
        status_animation.AutoReverse = True
        status_animation.RepeatBehavior = RepeatBehavior.Forever

        status_text.BeginAnimation(
            TextBlock.OpacityProperty,
            status_animation
        )

        dots_stack.Children.Add(status_text)
        border.Child = dots_stack

        # Start timer for rotating text
        self.current_message_index = 0
        self.typing_timer = DispatcherTimer()
        self.typing_timer.Interval = TimeSpan.FromSeconds(2.0)
        self.typing_timer.Tick += self.rotate_loading_message
        self.typing_timer.Start()

        # Wrap with bot avatar and set Name on container for removal
        container = self._wrap_with_avatar(border, is_user=False)
        container.Name = "TypingIndicator"
        self.messages_panel.Children.Add(container)
        # Store reference for updates
        self.typing_status_text = status_text

        # Scroll to bottom
        self.message_scrollviewer.ScrollToBottom()
    
    def replace_typing_with_response(self, text, sources):
        """Remove typing indicator and add actual response"""

        # Stop timer if running
        if hasattr(self, 'typing_timer') and self.typing_timer:
            self.typing_timer.Stop()
            self.typing_timer = None
            
        self._find_and_remove_typing_indicator()

        # Add the actual response
        self.add_message(text, is_user=False, sources=sources)
    
    def update_typing_status(self, status):
        """Update the typing indicator status text"""
        if hasattr(self, 'typing_status_text') and self.typing_status_text:
            self.Dispatcher.Invoke(
                lambda: setattr(self.typing_status_text, 'Text', status)
            )
    
    def _find_and_remove_typing_indicator(self):
        """Find and remove the typing indicator from messages panel"""
        for child in self.messages_panel.Children:
            if hasattr(child, 'Name') and child.Name == "TypingIndicator":
                self.messages_panel.Children.Remove(child)
                return True
        return False

    def start_streaming_response(self):
        """Remove typing indicator and create empty message bubble for streaming"""
        debug_log("start_streaming_response: called")
        # Stop timer if running
        if hasattr(self, 'typing_timer') and self.typing_timer:
            self.typing_timer.Stop()
            self.typing_timer = None

        self._find_and_remove_typing_indicator()

        # Create border (message bubble)
        border = Border()
        border.Style = self.FindResource("MessageBubbleAssistant")
        border.Name = "StreamingMessage"

        # Create text content
        textblock = TextBlock()
        textblock.TextWrapping = TextWrapping.Wrap
        textblock.Foreground = self.FindResource("TextPrimaryColor")
        textblock.Name = "StreamingTextBlock"

        border.Child = textblock

        # Create stack for content (will hold bubble + eventual sources)
        content_stack = StackPanel()
        content_stack.Children.Add(border)

        # Wrap with bot avatar
        container = self._wrap_with_avatar(content_stack, is_user=False)
        self.messages_panel.Children.Add(container)

        # Store references
        self.streaming_textblock = textblock
        self.streaming_border = border
        self.streaming_content_stack = content_stack
        self.streaming_text = u""
        
        debug_log("start_streaming_response: setup complete")
        # Scroll to bottom
        self.message_scrollviewer.ScrollToBottom()
    
    def append_to_streaming_response(self, text_chunk):
        """Append text chunk to streaming response"""
        try:
            if hasattr(self, 'streaming_textblock') and self.streaming_textblock:
                # Convert to Python unicode and sanitize to ASCII immediately
                from standards_chat.utils import safe_str, ascii_safe
                text_chunk = ascii_safe(safe_str(text_chunk))

                # Defensive: ensure streaming_text is also Python unicode
                if not isinstance(self.streaming_text, unicode):
                    self.streaming_text = ascii_safe(safe_str(self.streaming_text))

                # Now both are ASCII-safe Python unicode - safe to concatenate
                self.streaming_text = self.streaming_text + text_chunk

                # Re-render with formatting
                self.streaming_textblock.Inlines.Clear()
                self._add_formatted_text(self.streaming_textblock, self.streaming_text)

                # Scroll to bottom
                self.message_scrollviewer.ScrollToBottom()
            else:
                debug_log("append_to_streaming_response: streaming_textblock does not exist")
        except Exception as e:
            safe_print("ERROR in append_to_streaming_response: {}".format(safe_str(e)))
            # Log to file since pyRevit console may be disposed
            try:
                import os, io, traceback
                from standards_chat.utils import safe_str_ascii, ascii_safe
                from datetime import datetime
                log_dir = os.path.join(os.environ.get('APPDATA', ''), 'BBB', 'StandardsAssistant')
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                f = io.open(os.path.join(log_dir, 'error_log.txt'), 'a', encoding='utf-8')
                f.write(u"\n=== {} [append_to_streaming] ===\n".format(datetime.now().isoformat()))
                f.write(u"Error: {}\n".format(safe_str_ascii(e)))
                f.write(u"Traceback:\n{}\n".format(ascii_safe(traceback.format_exc())))
                f.close()
            except Exception:
                pass
    
    def finish_streaming_response(self, sources):
        """Add sources and apply formatting to completed streaming response"""
        try:
            if hasattr(self, 'streaming_textblock') and self.streaming_textblock:
                # Check for actions in the response FIRST
                actions = parse_action_from_response(self.streaming_text)
                
                # Remove JSON blocks from the displayed text
                import re
                display_text = self.streaming_text
                if actions:
                    # Remove all JSON code blocks
                    # Use unicode pattern to avoid encoding errors with input text
                    display_text = re.sub(u'```json\\s*\\{.*?\\}\\s*```', u'', display_text, flags=re.DOTALL)
                    # Clean up extra whitespace
                    display_text = re.sub(u'\n{3,}', u'\n\n', display_text)
                    display_text = display_text.strip()
                
                # Clear and reformat with markdown (WITHOUT the JSON)
                self.streaming_textblock.Inlines.Clear()
                self._add_formatted_text(self.streaming_textblock, display_text, sources=sources)
                
                # Add action buttons if enabled in settings
                actions_enabled = self.config.get('features', 'enable_actions', default=True)
                workflows_enabled = self.config.get('features', 'enable_workflows', default=True)
                
                if actions and self.action_executor and actions_enabled:
                    # Filter out workflows if they're disabled
                    if not workflows_enabled:
                        actions = [a for a in actions if a.get('type') != 'workflow']
                    
                    if actions:
                        self._add_action_buttons(self.streaming_border, actions)
                
                # Add subdued source links below bubble.
                # Do not show sources when the DCT fallback button is active --
                # those results are below the confidence threshold and would be misleading.
                show_dct = getattr(self, '_show_dct_button', False)
                if sources and not show_dct:
                    sources_panel = self._create_sources_panel(sources)
                    if sources_panel and hasattr(self, 'streaming_content_stack'):
                        self.streaming_content_stack.Children.Add(sources_panel)
                
                # Show DCT button only when search confidence was too low AND Claude
                # did not surface any sources in its response. If sources are present
                # the response was useful, so the fallback button should not appear.
                try:
                    if show_dct and not sources:
                        self._add_dct_ticket_panel()
                except Exception as detect_err:
                    safe_print(u"Error showing DCT panel: {}".format(safe_str(detect_err)))
                finally:
                    self._show_dct_button = False
            
            # Scroll to bottom
            self.message_scrollviewer.ScrollToBottom()
            
            # Clean up
            self.streaming_textblock = None
            self.streaming_border = None
            self.streaming_text = u""
        except Exception as e:
            from standards_chat.utils import safe_str_ascii
            safe_print("Error in finish_streaming_response: {}".format(safe_str_ascii(e)))
            # Don't crash processing, just finish up
            self.streaming_textblock = None
            self.streaming_border = None
            self.streaming_text = u""
    
    def _add_action_buttons(self, parent_border, actions):
        """Add action buttons to response bubble"""
        from System.Windows.Controls import Button, StackPanel
        
        # Clear any previously active action button
        self.active_action_button = None
        
        try:
            # Get the existing textblock and remove it from border
            existing_textblock = parent_border.Child
            parent_border.Child = None  # CRITICAL: Remove from border first!
            
            # Create new stack panel to hold text + buttons
            stack = StackPanel()
            stack.Children.Add(existing_textblock)
            
            # Add buttons for each action
            for i, action_data in enumerate(actions):
                button = Button()
                button.Content = action_data.get('label', 'Execute Action')
                button.Style = self.FindResource("ActionButtonStyle")
                
                # Store action data
                button.Tag = action_data
                
                # Wire up click event
                button.Click += self.on_action_button_click
                
                stack.Children.Add(button)
                
                # Set first button as active (can be triggered with Enter)
                if i == 0:
                    self.active_action_button = button
            
            # Set stack panel as border content
            parent_border.Child = stack
            
        except Exception as e:
            safe_print("Error in _add_action_buttons: {}".format(safe_str(e)))
    
    def on_action_button_click(self, sender, args):
        """Handle action button click"""
        from pyrevit import forms
        
        button = sender
        action_data = button.Tag
        
        # Disable button while executing
        button.IsEnabled = False
        original_content = button.Content
        button.Content = "Executing..."
        
        def on_action_complete(result):
            """Callback when action completes"""
            def update_ui():
                if result.get('success'):
                    # Format message based on whether it's a workflow or single action
                    if 'steps' in result:
                        # Workflow result - show summary
                        message = "✓ Workflow completed: {}\n".format(result['message'])
                        for i, step in enumerate(result['steps'], 1):
                            status = "✓" if step['success'] else "✗"
                            message += "\n  {} Step {}: {}".format(status, i, step['message'])
                        self.add_message(message, is_user=False)
                    else:
                        # Single action result
                        self.add_message(
                            "✓ Action completed: {}".format(result['message']),
                            is_user=False
                        )
                    button.Content = "✓ Completed"
                    button.Background = SolidColorBrush(Color.FromRgb(40, 167, 69))
                else:
                    forms.alert(
                        "Action failed:\n{}".format(result.get('message', 'Unknown error')),
                        title="Action Failed",
                        warn_icon=True
                    )
                    button.Content = "✗ Failed"
                    button.Background = SolidColorBrush(Color.FromRgb(220, 53, 69))
                    button.IsEnabled = True
            
            # Update UI on dispatcher thread
            try:
                self.Dispatcher.Invoke(System.Action(update_ui))
            except Exception as e:
                safe_print("Error updating UI: {}".format(safe_str(e)))
        
        try:
            # Check if this is a workflow
            if action_data.get('type') == 'workflow':
                # Extract the workflow steps
                workflow_steps = action_data.get('workflow', [])
                self.action_executor.execute_action(workflow_steps, callback=on_action_complete)
            else:
                # Execute single action with callback - ExternalEvent handles threading
                self.action_executor.execute_action(action_data, callback=on_action_complete)
        
        except Exception as e:
            from standards_chat.utils import safe_str_ascii
            forms.alert(
                "Error executing action:\n{}".format(safe_str_ascii(e)),
                title="Error",
                warn_icon=True
            )
            button.IsEnabled = True
            button.Content = original_content
    
    def enable_input(self):
        """Re-enable input controls"""
        self.input_textbox.IsEnabled = True
        # Only enable send button if there's text in the input
        self.send_button.IsEnabled = len(self.input_textbox.Text.strip()) > 0
        self.input_textbox.Focus()
    
    def add_message(self, text, is_user=False, sources=None):
        """Add a message bubble with avatar to the chat"""
        # Create border (message bubble)
        border = Border()

        # Set style based on user/assistant
        if is_user:
            border.Style = self.FindResource("MessageBubbleUser")
            text_color = SolidColorBrush(Color.FromRgb(255, 255, 255))
        else:
            border.Style = self.FindResource("MessageBubbleAssistant")
            text_color = self.FindResource("TextPrimaryColor")

        # Create text content with basic markdown formatting
        textblock = TextBlock()
        textblock.TextWrapping = TextWrapping.Wrap
        textblock.Foreground = text_color
        if is_user:
            textblock.FontWeight = System.Windows.FontWeights.SemiBold

        # Basic markdown parsing for assistant messages
        if False: # Disabled for user messages too if we want markdown there
             pass
             
        if not is_user:
            self._add_formatted_text(textblock, text)
        else:
            # User messages are plain text
            textblock.Inlines.Add(Run(text))

        # Add subdued source links (Legacy path, now mostly handled by finish_streaming_response)
        if sources and not is_user:
             # This legacy method added them inside the bubble.
             # We prefer the separate panel created in finish_streaming_response
             pass 

        border.Child = textblock

        # Wrap with avatar and add to panel
        container = self._wrap_with_avatar(border, is_user)
        self.messages_panel.Children.Add(container)
        
        # If we have sources and it's not user, add the panel below
        if sources and not is_user:
             panel = self._create_sources_panel(sources)
             if panel:
                 # We need to add it to the bubble stack which is inside the container
                 # _wrap_with_avatar returns Grid(Avatar, StackPanel(Bubble)) for assistant columns.
                 # The StackPanel is the second child (index 1).
                 try:
                     from System.Windows.Controls import StackPanel
                     bubble_stack = container.Children[1]
                     if isinstance(bubble_stack, StackPanel):
                         bubble_stack.Children.Add(panel)
                 except Exception as e:
                     logger.error("Error appending sources panel in add_message: {}".format(e))
                     pass

        # Scroll to bottom
        self.message_scrollviewer.ScrollToBottom()
    
    def _add_formatted_text(self, textblock, text, sources=None):
        """Add text with basic markdown formatting"""
        try:
            from standards_chat.utils import ascii_safe, safe_str_ascii
            
            # CRITICAL: Ensure text is ASCII-safe BEFORE any processing
            text = ascii_safe(text)
            
            import re
            
            lines = text.split(u'\n')
            
            for i, line in enumerate(lines):
                if i > 0:
                    textblock.Inlines.Add(Run(u"\n"))
                
                # Handle headers (make bold and slightly larger)
                if line.strip().startswith(u'#'):
                    header_text = line.strip().lstrip(u'#').strip()
                    run = Run(u"\n" + header_text + u"\n")
                    run.FontWeight = System.Windows.FontWeights.Bold
                    run.FontSize = 15
                    textblock.Inlines.Add(run)
                    continue
                    
                # Handle bullet points - USE ASCII ONLY
                prefix = u""
                content = line
                if line.strip().startswith(u'- ') or line.strip().startswith(u'* '):
                    prefix = u"  * "  # Use ASCII asterisk instead of Unicode bullet
                    content = line.strip()[2:]
                # Handle numbered lists
                elif re.match(u'^\\d+\\.\\s', line.strip()):
                    match = re.match(u'^(\\d+\\.\\s)(.*)', line.strip())
                    prefix = u"  " + match.group(1)
                    content = match.group(2)
                
                if prefix:
                    textblock.Inlines.Add(Run(prefix))
                
                try:
                    # Process inline formatting (Bold, Links, Citations)
                    # Regex for markdown links: [text](url)
                    # Regex for citations: [1], [15], etc.
                    # Split pattern captures all interesting parts
                    # Capture groups: 1=Link, 2=Citation, 3=RawURL
                    
                    split_pattern = u'(\\[[^\\]]+\\]\\([^)]+\\))|(\\[\\d+\\])|(https?://[^\\s]+)'
                    parts = re.split(split_pattern, content)
                
                    for part in parts:
                        if not part: continue
                        
                        # Ensure every part is ASCII-safe before processing
                        part = ascii_safe(part)
                        
                        # Case 1: Citations [1]
                        citation_match = re.match(u'^\\[(\\d+)\\]$', part)
                        if citation_match:
                            index = int(citation_match.group(1))
                            
                            # Create small citation link
                            hlink = Hyperlink()
                            hlink.TextDecorations = None
                            hlink.Foreground = self.FindResource("PrimaryColor")
                            
                            # Try to get tooltip from sources
                            tooltip_text = "Source " + str(index)
                            target_url = None
                            
                            if sources and index > 0 and index <= len(sources):
                                source = sources[index-1]
                                title = source.get('title', 'Unknown')
                                # Clean title
                                if title.lower().endswith(" - sharepoint page"): title = title[:-17]
                                elif title.lower().endswith(" sharepoint page"): title = title[:-16]
                                # Ensure title is ASCII-safe for tooltip
                                tooltip_text = ascii_safe(title)
                                target_url = source.get('url')
                                
                            hlink.ToolTip = tooltip_text
                            
                            # Make clickable if we have a URL
                            if target_url:
                                hlink.NavigateUri = System.Uri(target_url)
                                hlink.RequestNavigate += self.on_hyperlink_click
                                hlink.Cursor = System.Windows.Input.Cursors.Hand

                            # Content
                            run = Run(part)
                            run.FontSize = 10 
                            run.FontWeight = System.Windows.FontWeights.SemiBold
                            # run.BaselineAlignment = System.Windows.BaselineAlignment.Superscript
                            hlink.Inlines.Add(run)
                            
                            textblock.Inlines.Add(hlink)
                            continue

                        # Case 2: Markdown Links [text](url)
                        link_match = re.match(u'\\[([^\\]]+)\\]\\(([^)]+)\\)', part)
                        if link_match:
                            link_text = link_match.group(1)
                            link_url = link_match.group(2)
                            
                            hyperlink = Hyperlink()
                            hyperlink.Inlines.Add(Run(link_text))
                            try:
                                hyperlink.NavigateUri = System.Uri(link_url)
                                hyperlink.RequestNavigate += self.on_hyperlink_click
                                hyperlink.Foreground = self.FindResource("PrimaryColor")
                                textblock.Inlines.Add(hyperlink)
                            except:
                                textblock.Inlines.Add(Run(link_text))
                            continue
                            
                        # Case 3: Raw URLs
                        if re.match(u'^https?://', part):
                            hyperlink = Hyperlink()
                            hyperlink.Inlines.Add(Run(part))
                            try:
                                hyperlink.NavigateUri = System.Uri(part)
                                hyperlink.RequestNavigate += self.on_hyperlink_click
                                hyperlink.Foreground = self.FindResource("PrimaryColor")
                                textblock.Inlines.Add(hyperlink)
                            except:
                                textblock.Inlines.Add(Run(part))
                            continue
                        
                        # Case 4: Plain text with bold
                        if u'**' in part:
                            bold_parts = re.split(u'(\\*\\*.*?\\*\\*)', part)
                            for bold_part in bold_parts:
                                if bold_part.startswith(u'**') and bold_part.endswith(u'**'):
                                    run = Run(bold_part[2:-2])
                                    run.FontWeight = System.Windows.FontWeights.Bold
                                    textblock.Inlines.Add(run)
                                elif bold_part:
                                    textblock.Inlines.Add(Run(bold_part))
                        else:
                            textblock.Inlines.Add(Run(part))
                            
                except Exception as line_error:
                    safe_print(u"ERROR processing line in _add_formatted_text: {}".format(safe_str_ascii(line_error)))
                    # Add the line as plain text if formatting fails
                    try:
                        textblock.Inlines.Add(Run(ascii_safe(line)))
                    except:
                        pass
        except Exception as e:
            safe_print(u"ERROR in _add_formatted_text: {}".format(safe_str_ascii(e)))
            import traceback
            safe_print(u"Traceback: {}".format(safe_str_ascii(traceback.format_exc())))
            # Add text as plain if formatting completely fails
            try:
                textblock.Inlines.Add(Run(ascii_safe(text)))
            except:
                textblock.Inlines.Add(Run(u"<Error displaying text>"))
    
    def on_hyperlink_click(self, sender, args):
        """Open hyperlink in browser"""
        import webbrowser
        try:
            webbrowser.open(args.Uri.ToString())
        except Exception as e:
            safe_print("Error opening link: " + safe_str(e))
        args.Handled = True
    
    def _add_dct_ticket_panel(self):
        """Add DCT support button inside the chat bubble with a rotating message"""
        try:
            if not hasattr(self, 'streaming_border') or not self.streaming_border:
                return

            from System.Windows.Controls import StackPanel, Button, Separator
            from System.Windows.Documents import Run

            # Rotating playful messages
            messages = [
                u"Hmm, I'm stumped. Maybe it's time to ask the humans!",
                u"This one's beyond me -- the DCT team will know!",
                u"I've hit my limit. The real experts can help from here.",
                u"Not in my notes! Let's get a human on this one.",
                u"Time to phone a friend? DCT's got your back.",
                u"Even I have my blind spots. The team can help!",
                u"I wish I knew! DCT will have the answer though.",
            ]
            message = messages[random.randint(0, len(messages) - 1)]

            # Get existing content from the bubble border
            existing_child = self.streaming_border.Child
            self.streaming_border.Child = None

            # Create stack to hold text + divider + CTA inside the bubble
            inner_stack = StackPanel()
            inner_stack.Children.Add(existing_child)

            # Subtle divider line
            divider = Border()
            divider.Height = 1
            divider.Background = SolidColorBrush(Color.FromRgb(0xE0, 0xE0, 0xE0))
            divider.Margin = Thickness(0, 12, 0, 10)
            inner_stack.Children.Add(divider)

            # Message text
            msg_text = TextBlock()
            msg_text.Text = message
            msg_text.TextWrapping = TextWrapping.Wrap
            msg_text.FontSize = 12
            msg_text.FontStyle = System.Windows.FontStyles.Italic
            msg_text.Foreground = SolidColorBrush(Color.FromRgb(0x60, 0x60, 0x60))
            msg_text.Margin = Thickness(0, 0, 0, 8)
            inner_stack.Children.Add(msg_text)

            # Button with rounded corners via ControlTemplate
            from System.Windows.Controls import ControlTemplate, ContentPresenter
            from System.Windows.Markup import XamlReader as BtnXamlReader

            button = Button()
            button.Background = self.FindResource("PrimaryColor")
            button.Foreground = Brushes.White
            button.Padding = Thickness(14, 8, 16, 8)
            button.BorderThickness = Thickness(0)
            button.HorizontalAlignment = HorizontalAlignment.Left
            button.Cursor = System.Windows.Input.Cursors.Hand

            # Rounded corner template
            template_xaml = u"""<ControlTemplate
                xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
                xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
                TargetType="Button">
                <Border x:Name="border"
                        Background="{TemplateBinding Background}"
                        CornerRadius="6"
                        Padding="{TemplateBinding Padding}">
                    <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
                </Border>
                <ControlTemplate.Triggers>
                    <Trigger Property="IsEnabled" Value="False">
                        <Setter Property="Opacity" Value="0.6"/>
                    </Trigger>
                </ControlTemplate.Triggers>
            </ControlTemplate>"""
            button.Template = BtnXamlReader.Parse(template_xaml)

            # Button content: icon + text in a horizontal stack
            btn_content = StackPanel()
            btn_content.Orientation = Orientation.Horizontal

            # Small arrow/external-link icon
            icon_text = TextBlock()
            icon_text.Text = u">"
            icon_text.FontSize = 12
            icon_text.FontWeight = System.Windows.FontWeights.Bold
            icon_text.Foreground = Brushes.White
            icon_text.Margin = Thickness(0, 0, 6, 0)
            icon_text.VerticalAlignment = System.Windows.VerticalAlignment.Center
            btn_content.Children.Add(icon_text)

            label_text = TextBlock()
            label_text.Text = u"Open a Ticket with DCT"
            label_text.FontSize = 12
            label_text.FontWeight = System.Windows.FontWeights.SemiBold
            label_text.Foreground = Brushes.White
            label_text.VerticalAlignment = System.Windows.VerticalAlignment.Center
            btn_content.Children.Add(label_text)

            button.Content = btn_content

            # Store ticket URL in button tag
            button.Tag = u"https://portal.bbbarch.com/a/tickets/new"
            button.Click += self._on_dct_button_click

            # Hover effects
            normal_bg = self.FindResource("PrimaryColor")
            hover_bg = SolidColorBrush(Color.FromRgb(0x00, 0x5A, 0x9E))
            button.MouseEnter += lambda s, e: s.SetValue(Button.BackgroundProperty, hover_bg)
            button.MouseLeave += lambda s, e: s.SetValue(Button.BackgroundProperty, normal_bg)

            inner_stack.Children.Add(button)

            # Put the stack back inside the bubble
            self.streaming_border.Child = inner_stack

        except Exception as e:
            safe_print(u"Error creating DCT ticket panel (non-critical): {}".format(safe_str(e))[:200])
    
    def _on_dct_button_click(self, sender, args):
        """Handle DCT ticket button click"""
        import webbrowser
        try:
            button = sender
            url = button.Tag
            webbrowser.open(str(url))
        except Exception as e:
            safe_print(u"Error opening DCT ticket link: {}".format(safe_str(e)))
    
    def show_loading(self, status="Loading..."):
        """Show loading overlay with animated spinner"""
        self.loading_overlay.Visibility = System.Windows.Visibility.Visible
        self.loading_status_text.Text = status
        self.send_button.IsEnabled = False
        self.input_textbox.IsEnabled = False
        
        # Start spinner animation
        self.spin_animation = DoubleAnimation()
        self.spin_animation.From = 0.0
        self.spin_animation.To = 360.0
        self.spin_animation.Duration = Duration(TimeSpan.FromSeconds(1.5))
        self.spin_animation.RepeatBehavior = RepeatBehavior.Forever
        self.spinner_rotation.BeginAnimation(
            System.Windows.Media.RotateTransform.AngleProperty,
            self.spin_animation
        )
    
    def hide_loading(self):
        """Hide loading overlay and stop spinner"""
        # Stop spinner animation
        if self.spinner_rotation:
            self.spinner_rotation.BeginAnimation(
                System.Windows.Media.RotateTransform.AngleProperty,
                None
            )
        
        self.loading_overlay.Visibility = System.Windows.Visibility.Collapsed
        self.send_button.IsEnabled = True
        self.input_textbox.IsEnabled = True
        self.input_textbox.Focus()
    
    def update_loading_status(self, status):
        """Update loading status text"""
        self.Dispatcher.Invoke(
            lambda: setattr(self.loading_status_text, 'Text', status)
        )
