# -*- coding: utf-8 -*-
"""
Chat Window Controller
Manages the WPF window, user interactions, and coordinates API calls
"""

import clr
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
from System.Windows.Threading import Dispatcher
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

from standards_chat.notion_client import NotionClient
from standards_chat.anthropic_client import AnthropicClient
from standards_chat.config_manager import ConfigManager
from standards_chat.utils import extract_revit_context
from standards_chat.usage_logger import UsageLogger
from standards_chat.revit_actions import RevitActionExecutor, parse_action_from_response
from standards_chat.history_manager import HistoryManager


class StandardsChatWindow(Window):
    """Main chat window for Kodama"""
    
    def __init__(self):
        """Initialize the chat window"""
        # Load XAML
        xaml_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'ui', 'chat_window.xaml'
        )
        with open(xaml_path, 'r') as f:
            xaml_content = f.read()
        
        # Parse XAML - this creates a complete window
        window = XamlReader.Parse(xaml_content)
        
        # Copy all properties from parsed window to self
        self.Title = window.Title
        self.Height = window.Height
        self.Width = window.Width
        self.MinHeight = window.MinHeight
        self.MinWidth = window.MinWidth
        self.WindowStartupLocation = window.WindowStartupLocation
        self.Background = window.Background
        self.Content = window.Content
        self.Resources = window.Resources
        
        # Get UI elements from the parsed window's content tree
        self.messages_panel = window.FindName('MessagesPanel')
        self.input_textbox = window.FindName('InputTextBox')
        self.send_button = window.FindName('SendButton')
        self.status_text = window.FindName('StatusText')
        self.loading_overlay = window.FindName('LoadingOverlay')
        self.loading_status_text = window.FindName('LoadingStatusText')
        self.message_scrollviewer = window.FindName('MessageScrollViewer')
        self.spinner_rotation = window.FindName('SpinnerRotation')
        self.header_icon = window.FindName('HeaderIcon')
        self.header_icon_button = window.FindName('HeaderIconButton')
        self.ScreenshotToggle = window.FindName('ScreenshotToggle')
        
        # Sidebar elements
        self.sidebar = window.FindName('Sidebar')
        self.sidebar_column = window.FindName('SidebarColumn')
        self.toggle_sidebar_button = window.FindName('ToggleSidebarButton')
        self.new_chat_button = window.FindName('NewChatButton')
        self.history_listbox = window.FindName('HistoryListBox')
        
        # Load icon image
        self._load_header_icon()
        
        # Animation
        self.spin_animation = None
        
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
                    # Use dynamic import to avoid IronPython parsing issues
                    vector_db_module = __import__('standards_chat.vector_db_client', fromlist=['VectorDBClient'])
                    VectorDBClient = vector_db_module.VectorDBClient
                    temp_vdb = VectorDBClient(self.config)
                    if temp_vdb.is_developer_mode_enabled():
                        self.vector_db_client = temp_vdb
            except ImportError as e:
                # Vector search packages not installed - silently fall back to keyword search
                # This is expected if chromadb/openai packages aren't installed
                pass
            except Exception as e:
                # Other errors should be logged
                print("Vector DB initialization error: {}".format(str(e)))
            
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
                    with open(index_path, 'r') as f:
                        self.sharepoint_index = json.load(f)
            except Exception as e:
                print("Error loading SharePoint index: {}".format(str(e)))
            
        except Exception as e:
            # Show error in status
            self.status_text.Text = "Configuration Error: {}".format(str(e))
            self.send_button.IsEnabled = False
            return
        
        # Conversation history
        self.conversation = []
        
        # Session tracking
        self.current_session_id = None
        self.session_title = None
        
        # Track active action button
        self.active_action_button = None
        
        # Wire up events
        self.send_button.Click += self.on_send_click
        self.input_textbox.KeyDown += self.on_input_keydown
        self.toggle_sidebar_button.Click += self.on_toggle_sidebar_click
        self.new_chat_button.Click += self.on_new_chat_click
        self.history_listbox.SelectionChanged += self.on_history_selection_changed
        if self.header_icon_button:
            self.header_icon_button.Click += self.on_header_icon_click
        
        # Load chat history into sidebar
        self.Loaded += self.on_window_loaded
        
        # Focus input box
        self.Loaded += lambda s, e: self.input_textbox.Focus()
    
    def on_header_icon_click(self, sender, args):
        """Open the standards website"""
        try:
            from System.Diagnostics import Process, ProcessStartInfo
            psi = ProcessStartInfo("https://beyerblinderbelle.sharepoint.com/sites/revitstandards")
            psi.UseShellExecute = True
            Process.Start(psi)
        except Exception as e:
            print("Error opening URL: {}".format(str(e)))
    
    def _load_header_icon(self):
        """Load the icon from the button folder into the header"""
        try:
            # Find the icon path - go up from lib/standards_chat to BBB.extension root
            script_dir = os.path.dirname(__file__)  # lib/standards_chat
            lib_dir = os.path.dirname(script_dir)  # lib
            extension_dir = os.path.dirname(lib_dir)  # BBB.extension
            
            icon_path = os.path.join(
                extension_dir,
                'Chat.tab',
                'Kodama.panel',
                'Kodama.pushbutton',
                'icon.png'
            )
            
            
            if os.path.exists(icon_path):
                bitmap = BitmapImage()
                bitmap.BeginInit()
                bitmap.UriSource = Uri("file:///" + icon_path.replace("\\", "/"))
                bitmap.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad
                bitmap.EndInit()
                self.header_icon.Source = bitmap
            else:
                print("Icon file not found at: {}".format(icon_path))
        except Exception as e:
            # Print error for debugging
            print("Could not load header icon: {}".format(str(e)))
    
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
    
    def on_window_loaded(self, sender, args):
        """Handle window loaded event - populate history list"""
        self.refresh_history_list()
    
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
            print("Error deleting session: {}".format(str(e)))
    
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
        
        # Clear messages panel except welcome message
        while self.messages_panel.Children.Count > 1:
            self.messages_panel.Children.RemoveAt(1)
        
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
            grid.Margin = Thickness(0, 2, 0, 2)
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
            title_txt.TextTrimming = TextTrimming.CharacterEllipsis
            title_txt.Foreground = self.FindResource("TextPrimaryColor")
            title_txt.ToolTip = session['title']
            
            time_txt = TextBlock()
            # Format timestamp
            try:
                from datetime import datetime
                # Try parsing ISO format manually since fromisoformat is 3.7+
                # Format: YYYY-MM-DDTHH:MM:SS.mmmmmm
                ts = session['timestamp']
                if '.' in ts:
                    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f")
                else:
                    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
                time_txt.Text = dt.strftime('%b %d, %I:%M %p')
            except:
                time_txt.Text = session['timestamp']
            time_txt.FontSize = 10
            time_txt.Foreground = self.FindResource("TextSecondaryColor")
            time_txt.Margin = Thickness(0, 2, 0, 0)
            
            stack.Children.Add(title_txt)
            stack.Children.Add(time_txt)
            
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
        
        # Clear messages panel except welcome message
        while self.messages_panel.Children.Count > 1:
            self.messages_panel.Children.RemoveAt(1)
        
        # Re-render all messages
        for exchange in self.conversation:
            # Add user message
            self.add_message(exchange['user'], is_user=True)
            
            # Add assistant response
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
            revit_context = extract_revit_context()
        
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
                # print("DEBUG: process_query started")
                # Update status: Searching
                self.update_typing_status("Searching BBB's Revit standards...")
                
                # Extract keywords using index
                search_query = user_input
                keyword_tokens_in = 0
                keyword_tokens_out = 0
                
                if hasattr(self, 'sharepoint_index') and self.sharepoint_index:
                    # self.update_typing_status("Optimizing search query...")
                    keyword_result = self.anthropic.get_search_keywords(user_input, self.sharepoint_index)
                    
                    if isinstance(keyword_result, dict):
                        search_query = keyword_result.get('keywords', user_input)
                        keyword_tokens_in = keyword_result.get('input_tokens', 0)
                        keyword_tokens_out = keyword_result.get('output_tokens', 0)
                    else:
                        search_query = keyword_result
                    
                    # print("DEBUG: Optimized query: {}".format(search_query))
                
                # Search standards - use vector search if available
                # print("DEBUG: Calling search_standards")
                if self.vector_db_client is not None:
                    # Use hybrid vector search (semantic + keyword)
                    self.update_typing_status("Performing semantic search...")
                    relevant_pages = self.vector_db_client.hybrid_search(
                        query=user_input,  # Use original user input for semantic search
                        deduplicate=True
                    )
                    # print("DEBUG: Vector search returned {} pages".format(len(relevant_pages)))
                else:
                    # Fall back to standard SharePoint keyword search
                    relevant_pages = self.standards_client.search_standards(search_query)
                    # print("DEBUG: search_standards returned {} pages".format(len(relevant_pages)))
                
                # Update status: Found results
                if relevant_pages:
                    self.update_typing_status("Found {} page(s), analyzing content...".format(len(relevant_pages)))
                else:
                    self.update_typing_status("Preparing response...")
                
                # Update status: Generating
                self.update_typing_status("Generating response...")
                
                # Remove typing indicator and add empty message bubble for streaming
                self.Dispatcher.Invoke(self.start_streaming_response)
                
                # Callback for streaming chunks
                def on_chunk(text_chunk):
                    self.Dispatcher.Invoke(
                        lambda: self.append_to_streaming_response(text_chunk)
                    )
                
                # Get streaming response from Claude
                response = self.anthropic.get_response_stream(
                    user_query=user_input,
                    notion_pages=relevant_pages,
                    revit_context=revit_context,
                    conversation_history=self.conversation,
                    callback=on_chunk,
                    screenshot_base64=screenshot_base64
                )
                
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
                        print("Title generation failed: " + str(e))
                
                # Auto-save session after each exchange
                self.save_current_session()
                
                # Refresh history list to show updated session
                self.Dispatcher.Invoke(self.refresh_history_list)
                
                # Add sources to the message
                self.Dispatcher.Invoke(
                    lambda: self.finish_streaming_response(response['sources'])
                )
                
            except Exception as e:
                # print("DEBUG: Error in process_query: " + str(e))
                import traceback
                # traceback.print_exc()
                error_msg = "Sorry, I encountered an error: {}".format(str(e))
                self.Dispatcher.Invoke(
                    lambda: self.replace_typing_with_response(error_msg, None)
                )
            
            finally:
                # Re-enable input
                self.Dispatcher.Invoke(self.enable_input)
        
        # Start background thread
        thread = Thread(ThreadStart(process_query))
        thread.SetApartmentState(System.Threading.ApartmentState.STA)
        thread.IsBackground = True
        thread.Start()
    
    def add_typing_indicator(self):
        """Add animated typing indicator bubble with status text"""
        # Create border (message bubble)
        border = Border()
        border.Style = self.FindResource("MessageBubbleAssistant")
        border.Name = "TypingIndicator"
        
        # Create vertical stack for dots and status
        main_stack = StackPanel()
        main_stack.Orientation = Orientation.Vertical
        
        # Create container for dots
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
        
        # Create status text with pulsing animation
        status_text = TextBlock()
        status_text.Text = "Searching BBB's Revit standards..."
        status_text.FontSize = 11
        status_text.Foreground = self.FindResource("TextSecondaryColor")
        status_text.Margin = Thickness(0, 8, 0, 0)
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
        
        # Add to stacks
        main_stack.Children.Add(dots_stack)
        main_stack.Children.Add(status_text)
        
        border.Child = main_stack
        self.messages_panel.Children.Add(border)
        
        # Store reference for updates
        self.typing_status_text = status_text
        
        # Scroll to bottom
        self.message_scrollviewer.ScrollToBottom()
    
    def replace_typing_with_response(self, text, sources):
        """Remove typing indicator and add actual response"""
        # Find and remove typing indicator
        for child in self.messages_panel.Children:
            if hasattr(child, 'Name') and child.Name == "TypingIndicator":
                self.messages_panel.Children.Remove(child)
                break
        
        # Add the actual response
        self.add_message(text, is_user=False, sources=sources)
    
    def update_typing_status(self, status):
        """Update the typing indicator status text"""
        if hasattr(self, 'typing_status_text') and self.typing_status_text:
            self.Dispatcher.Invoke(
                lambda: setattr(self.typing_status_text, 'Text', status)
            )
    
    def start_streaming_response(self):
        """Remove typing indicator and create empty message bubble for streaming"""
        # Find and remove typing indicator
        for child in self.messages_panel.Children:
            if hasattr(child, 'Name') and child.Name == "TypingIndicator":
                self.messages_panel.Children.Remove(child)
                break
        
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
        self.messages_panel.Children.Add(border)
        
        # Store references
        self.streaming_textblock = textblock
        self.streaming_border = border
        self.streaming_text = ""
        
        # Scroll to bottom
        self.message_scrollviewer.ScrollToBottom()
    
    def append_to_streaming_response(self, text_chunk):
        """Append text chunk to streaming response"""
        if hasattr(self, 'streaming_textblock') and self.streaming_textblock:
            self.streaming_text += text_chunk
            
            # Re-render with formatting each time
            self.streaming_textblock.Inlines.Clear()
            self._add_formatted_text(self.streaming_textblock, self.streaming_text)
            
            # Scroll to bottom
            self.message_scrollviewer.ScrollToBottom()
    
    def finish_streaming_response(self, sources):
        """Add sources and apply formatting to completed streaming response"""
        if hasattr(self, 'streaming_textblock') and self.streaming_textblock:
            # Check for actions in the response FIRST
            actions = parse_action_from_response(self.streaming_text)
            
            # Remove JSON blocks from the displayed text
            import re
            display_text = self.streaming_text
            if actions:
                # Remove all JSON code blocks
                display_text = re.sub(r'```json\s*\{.*?\}\s*```', '', display_text, flags=re.DOTALL)
                # Clean up extra whitespace
                display_text = re.sub(r'\n{3,}', '\n\n', display_text)
                display_text = display_text.strip()
            
            # Clear and reformat with markdown (WITHOUT the JSON)
            self.streaming_textblock.Inlines.Clear()
            self._add_formatted_text(self.streaming_textblock, display_text)
            
            # Add action buttons if enabled in settings
            actions_enabled = self.config.get('features', 'enable_actions', default=True)
            workflows_enabled = self.config.get('features', 'enable_workflows', default=True)
            
            if actions and self.action_executor and actions_enabled:
                # Filter out workflows if they're disabled
                if not workflows_enabled:
                    actions = [a for a in actions if a.get('type') != 'workflow']
                
                if actions:
                    self._add_action_buttons(self.streaming_border, actions)
            
            # Add sources with special formatting
            if sources:
                # Add divider line
                self.streaming_textblock.Inlines.Add(Run("\n\n"))
                divider = Run("─" * 40)
                divider.Foreground = self.FindResource("BorderColor")
                self.streaming_textblock.Inlines.Add(divider)
                
                # Add "Sources" header
                self.streaming_textblock.Inlines.Add(Run("\n\n"))
                header = Run("📚 Reference Documents")
                header.FontWeight = System.Windows.FontWeights.Bold
                header.FontSize = 13
                header.Foreground = self.FindResource("PrimaryColor")
                self.streaming_textblock.Inlines.Add(header)
                self.streaming_textblock.Inlines.Add(Run("\n"))
                
                # Add each source with icon and styling
                for source in sources:
                    self.streaming_textblock.Inlines.Add(Run("\n"))
                    
                    # Bullet/icon
                    bullet = Run("→ ")
                    bullet.Foreground = self.FindResource("PrimaryColor")
                    bullet.FontWeight = System.Windows.FontWeights.Bold
                    self.streaming_textblock.Inlines.Add(bullet)
                    
                    # Create hyperlink
                    hyperlink = Hyperlink()
                    hyperlink.Inlines.Add(Run(source['title']))
                    hyperlink.NavigateUri = System.Uri(source['url'])
                    hyperlink.RequestNavigate += self.on_hyperlink_click
                    hyperlink.Foreground = self.FindResource("PrimaryColor")
                    hyperlink.TextDecorations = None  # Remove underline until hover
                    
                    self.streaming_textblock.Inlines.Add(hyperlink)
                    
                    # Add category if available
                    if source.get('category'):
                        category_text = Run(" [{}]".format(source['category']))
                        category_text.FontSize = 10
                        category_text.Foreground = self.FindResource("TextSecondaryColor")
                        self.streaming_textblock.Inlines.Add(category_text)
            
            # Scroll to bottom
            self.message_scrollviewer.ScrollToBottom()
            
            # Clean up
            self.streaming_textblock = None
            self.streaming_border = None
            self.streaming_text = ""
    
    def _add_action_buttons(self, parent_border, actions):
        """Add action buttons to response bubble"""
        print("DEBUG: _add_action_buttons called with {} actions".format(len(actions)))
        
        from System.Windows.Controls import Button, StackPanel
        
        # Clear any previously active action button
        self.active_action_button = None
        
        try:
            # Get the existing textblock and remove it from border
            existing_textblock = parent_border.Child
            parent_border.Child = None  # CRITICAL: Remove from border first!
            print("DEBUG: Got existing textblock and removed from border")
            
            # Create new stack panel to hold text + buttons
            stack = StackPanel()
            stack.Children.Add(existing_textblock)
            print("DEBUG: Created stack panel and added textblock")
            
            # Add buttons for each action
            for i, action_data in enumerate(actions):
                print("DEBUG: Creating button {} for action type: {}".format(
                    i, action_data.get('type', 'unknown')
                ))
                button = Button()
                button.Content = action_data.get('label', 'Execute Action')
                button.Style = self.FindResource("ActionButtonStyle")
                
                # Store action data
                button.Tag = action_data
                
                # Wire up click event
                button.Click += self.on_action_button_click
                
                stack.Children.Add(button)
                print("DEBUG: Button {} added to stack".format(i))
                
                # Set first button as active (can be triggered with Enter)
                if i == 0:
                    self.active_action_button = button
            
            # Set stack panel as border content
            parent_border.Child = stack
            print("DEBUG: Stack panel set as border child - {} children total".format(stack.Children.Count))
            
        except Exception as e:
            print("DEBUG: Error in _add_action_buttons: {}".format(str(e)))
            import traceback
            traceback.print_exc()
    
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
                print("Error updating UI: {}".format(str(e)))
        
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
            forms.alert(
                "Error executing action:\n{}".format(str(e)),
                title="Error",
                warn_icon=True
            )
            button.IsEnabled = True
            button.Content = original_content
    
    def enable_input(self):
        """Re-enable input controls"""
        self.send_button.IsEnabled = True
        self.input_textbox.IsEnabled = True
        self.input_textbox.Focus()
    
    def add_message(self, text, is_user=False, sources=None):
        """Add a message bubble to the chat"""
        # Create border (message bubble)
        border = Border()
        
        # Set style based on user/assistant
        if is_user:
            border.Style = self.FindResource("MessageBubbleUser")
            text_color = Brushes.White
        else:
            border.Style = self.FindResource("MessageBubbleAssistant")
            text_color = self.FindResource("TextPrimaryColor")
        
        # Create text content with basic markdown formatting
        textblock = TextBlock()
        textblock.TextWrapping = TextWrapping.Wrap
        textblock.Foreground = text_color
        
        # Basic markdown parsing for assistant messages
        if not is_user:
            self._add_formatted_text(textblock, text)
        else:
            textblock.Inlines.Add(Run(text))
        
        # Add sources if present
        if sources and not is_user:
            # Add divider line
            textblock.Inlines.Add(Run("\n\n"))
            divider = Run("─" * 40)
            divider.Foreground = self.FindResource("BorderColor")
            textblock.Inlines.Add(divider)
            
            # Add "Sources" header
            textblock.Inlines.Add(Run("\n\n"))
            header = Run("📚 Reference Documents")
            header.FontWeight = System.Windows.FontWeights.Bold
            header.FontSize = 13
            header.Foreground = self.FindResource("PrimaryColor")
            textblock.Inlines.Add(header)
            textblock.Inlines.Add(Run("\n"))
            
            # Add each source with icon and styling
            for source in sources:
                textblock.Inlines.Add(Run("\n"))
                
                # Bullet/icon
                bullet = Run("→ ")
                bullet.Foreground = self.FindResource("PrimaryColor")
                bullet.FontWeight = System.Windows.FontWeights.Bold
                textblock.Inlines.Add(bullet)
                
                # Create hyperlink
                hyperlink = Hyperlink()
                hyperlink.Inlines.Add(Run(source['title']))
                hyperlink.NavigateUri = System.Uri(source['url'])
                hyperlink.RequestNavigate += self.on_hyperlink_click
                hyperlink.Foreground = self.FindResource("PrimaryColor")
                hyperlink.TextDecorations = None  # Remove underline until hover
                
                textblock.Inlines.Add(hyperlink)
                
                # Add category if available
                if source.get('category'):
                    category_text = Run(" [{}]".format(source['category']))
                    category_text.FontSize = 10
                    category_text.Foreground = self.FindResource("TextSecondaryColor")
                    textblock.Inlines.Add(category_text)
        
        border.Child = textblock
        
        # Add to panel
        self.messages_panel.Children.Add(border)
        
        # Scroll to bottom
        self.message_scrollviewer.ScrollToBottom()
    
    def _add_formatted_text(self, textblock, text):
        """Add text with basic markdown formatting"""
        import re
        
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if i > 0:
                textblock.Inlines.Add(Run("\n"))
            
            # Handle headers (make bold and slightly larger)
            if line.strip().startswith('#'):
                header_text = line.strip().lstrip('#').strip()
                run = Run("\n" + header_text + "\n")
                run.FontWeight = System.Windows.FontWeights.Bold
                run.FontSize = 15
                textblock.Inlines.Add(run)
                continue
                
            # Handle bullet points
            prefix = ""
            content = line
            if line.strip().startswith('- ') or line.strip().startswith('* '):
                prefix = "  • "
                content = line.strip()[2:]
            # Handle numbered lists
            elif re.match(r'^\d+\.\s', line.strip()):
                match = re.match(r'^(\d+\.\s)(.*)', line.strip())
                prefix = "  " + match.group(1)
                content = match.group(2)
            
            if prefix:
                textblock.Inlines.Add(Run(prefix))
            
            # Process inline formatting (Bold and Links)
            # Regex for markdown links: [text](url)
            link_pattern = r'(\[[^\]]+\]\([^)]+\))'
            parts = re.split(link_pattern, content)
            
            for part in parts:
                # Check if it's a markdown link
                link_match = re.match(r'\[([^\]]+)\]\(([^)]+)\)', part)
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
                else:
                    # Check for raw URLs in the text part
                    # Regex for raw URLs: http://... or https://...
                    url_pattern = r'(https?://[^\s]+)'
                    sub_parts = re.split(url_pattern, part)
                    
                    for sub_part in sub_parts:
                        if re.match(url_pattern, sub_part):
                            # It's a raw URL
                            hyperlink = Hyperlink()
                            hyperlink.Inlines.Add(Run(sub_part)) # Display the URL itself
                            try:
                                hyperlink.NavigateUri = System.Uri(sub_part)
                                hyperlink.RequestNavigate += self.on_hyperlink_click
                                hyperlink.Foreground = self.FindResource("PrimaryColor")
                                textblock.Inlines.Add(hyperlink)
                            except:
                                textblock.Inlines.Add(Run(sub_part))
                        else:
                            # Process bold in non-link text
                            if '**' in sub_part:
                                bold_parts = re.split(r'(\*\*.*?\*\*)', sub_part)
                                for bold_part in bold_parts:
                                    if bold_part.startswith('**') and bold_part.endswith('**'):
                                        run = Run(bold_part[2:-2])
                                        run.FontWeight = System.Windows.FontWeights.Bold
                                        textblock.Inlines.Add(run)
                                    elif bold_part:
                                        textblock.Inlines.Add(Run(bold_part))
                            else:
                                if sub_part:
                                    textblock.Inlines.Add(Run(sub_part))
    
    def on_hyperlink_click(self, sender, args):
        """Open hyperlink in browser"""
        import webbrowser
        webbrowser.open(str(args.Uri))
        args.Handled = True
    
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
