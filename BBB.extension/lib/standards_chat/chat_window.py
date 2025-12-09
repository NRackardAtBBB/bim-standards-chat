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


class StandardsChatWindow(Window):
    """Main chat window for standards assistant"""
    
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
            
            # Initialize usage logger
            central_log_path = self.config.get('logging', 'central_log_path')
            self.usage_logger = UsageLogger(
                central_log_path=central_log_path
            )
            
            # Initialize action executor
            try:
                from pyrevit import revit
                self.action_executor = RevitActionExecutor(revit.doc, revit.uidoc)
            except:
                self.action_executor = None
        except Exception as e:
            # Show error in status
            self.status_text.Text = "Configuration Error: {}".format(str(e))
            self.send_button.IsEnabled = False
            return
        
        # Conversation history
        self.conversation = []
        
        # Track active action button
        self.active_action_button = None
        
        # Wire up events
        self.send_button.Click += self.on_send_click
        self.input_textbox.KeyDown += self.on_input_keydown
        
        # Focus input box
        self.Loaded += lambda s, e: self.input_textbox.Focus()
    
    def _load_header_icon(self):
        """Load the icon from the button folder into the header"""
        try:
            # Find the icon path - go up from lib/standards_chat to BBB.extension root
            script_dir = os.path.dirname(__file__)  # lib/standards_chat
            lib_dir = os.path.dirname(script_dir)  # lib
            extension_dir = os.path.dirname(lib_dir)  # BBB.extension
            
            icon_path = os.path.join(
                extension_dir,
                'BBB.tab',
                'Standards Assistant.panel',
                'Standards Chat.pushbutton',
                'icon.dark.png'
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
    
    def send_message(self):
        """Send user message and get response"""
        user_input = self.input_textbox.Text.strip()
        
        if not user_input:
            return
        
        # Clear active action button when starting new query
        self.active_action_button = None
        
        # Track query start time for logging
        query_start_time = time.time()
        
        # Extract Revit context BEFORE starting background thread (must be on STA thread)
        # Only if enabled in settings
        revit_context = None
        if self.config.get('features', 'include_context', default=True):
            revit_context = extract_revit_context()
        
        # Capture screenshot if enabled
        from .utils import capture_revit_screenshot
        screenshot_base64 = None
        if self.config.get('features', 'include_screenshot', default=True):
            screenshot_base64 = capture_revit_screenshot()
        
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
                
                # Search standards
                # print("DEBUG: Calling search_standards")
                relevant_pages = self.standards_client.search_standards(user_input)
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
                
                # Calculate duration and log interaction
                duration_seconds = time.time() - query_start_time
                try:
                    self.usage_logger.log_interaction(
                        query=user_input,
                        response_preview=response.get('text', '')[:100],
                        source_count=len(response.get('sources', [])),
                        duration_seconds=duration_seconds,
                        revit_context=revit_context
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
        border.CornerRadius = System.Windows.CornerRadius(8)
        border.Padding = Thickness(12)
        border.Margin = Thickness(10, 5, 50, 5)
        border.HorizontalAlignment = HorizontalAlignment.Left
        border.Background = Brushes.White
        border.BorderBrush = SolidColorBrush(Color.FromRgb(224, 224, 224))
        border.BorderThickness = Thickness(1)
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
            dot.Fill = SolidColorBrush(Color.FromRgb(120, 120, 120))
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
        status_text.Foreground = SolidColorBrush(Color.FromRgb(120, 120, 120))
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
        border.CornerRadius = System.Windows.CornerRadius(8)
        border.Padding = Thickness(12)
        border.Margin = Thickness(10, 5, 50, 5)
        border.HorizontalAlignment = HorizontalAlignment.Left
        border.Background = Brushes.White
        border.BorderBrush = SolidColorBrush(Color.FromRgb(224, 224, 224))
        border.BorderThickness = Thickness(1)
        border.Name = "StreamingMessage"
        
        # Create text content
        textblock = TextBlock()
        textblock.TextWrapping = TextWrapping.Wrap
        textblock.Foreground = SolidColorBrush(Color.FromRgb(51, 51, 51))
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
                divider.Foreground = SolidColorBrush(Color.FromRgb(224, 224, 224))
                self.streaming_textblock.Inlines.Add(divider)
                
                # Add "Sources" header
                self.streaming_textblock.Inlines.Add(Run("\n\n"))
                header = Run("📚 Reference Documents")
                header.FontWeight = System.Windows.FontWeights.Bold
                header.FontSize = 13
                header.Foreground = SolidColorBrush(Color.FromRgb(42, 125, 225))
                self.streaming_textblock.Inlines.Add(header)
                self.streaming_textblock.Inlines.Add(Run("\n"))
                
                # Add each source with icon and styling
                for source in sources:
                    self.streaming_textblock.Inlines.Add(Run("\n"))
                    
                    # Bullet/icon
                    bullet = Run("→ ")
                    bullet.Foreground = SolidColorBrush(Color.FromRgb(42, 125, 225))
                    bullet.FontWeight = System.Windows.FontWeights.Bold
                    self.streaming_textblock.Inlines.Add(bullet)
                    
                    # Create hyperlink
                    hyperlink = Hyperlink()
                    hyperlink.Inlines.Add(Run(source['title']))
                    hyperlink.NavigateUri = System.Uri(source['url'])
                    hyperlink.RequestNavigate += self.on_hyperlink_click
                    hyperlink.Foreground = SolidColorBrush(Color.FromRgb(42, 125, 225))
                    hyperlink.TextDecorations = None  # Remove underline until hover
                    
                    self.streaming_textblock.Inlines.Add(hyperlink)
                    
                    # Add category if available
                    if source.get('category'):
                        category_text = Run(" [{}]".format(source['category']))
                        category_text.FontSize = 10
                        category_text.Foreground = SolidColorBrush(Color.FromRgb(120, 120, 120))
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
                button.Margin = Thickness(0, 10, 0, 0)
                button.Padding = Thickness(15, 8, 15, 8)
                button.Background = SolidColorBrush(Color.FromRgb(42, 125, 225))
                button.Foreground = Brushes.White
                button.BorderThickness = Thickness(0)
                button.Cursor = System.Windows.Input.Cursors.Hand
                
                # Add hover effect
                button.FontWeight = System.Windows.FontWeights.Normal
                
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
        border.CornerRadius = System.Windows.CornerRadius(8)
        border.Padding = Thickness(12)
        border.Margin = Thickness(
            50 if is_user else 10,
            5,
            10 if is_user else 50,
            5
        )
        border.HorizontalAlignment = \
            HorizontalAlignment.Right if is_user else HorizontalAlignment.Left
        
        # Set colors
        if is_user:
            border.Background = SolidColorBrush(Color.FromRgb(42, 125, 225))  # Blue
            text_color = Brushes.White
        else:
            border.Background = Brushes.White
            border.BorderBrush = SolidColorBrush(Color.FromRgb(224, 224, 224))
            border.BorderThickness = Thickness(1)
            text_color = SolidColorBrush(Color.FromRgb(51, 51, 51))
        
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
            divider.Foreground = SolidColorBrush(Color.FromRgb(224, 224, 224))
            textblock.Inlines.Add(divider)
            
            # Add "Sources" header
            textblock.Inlines.Add(Run("\n\n"))
            header = Run("📚 Reference Documents")
            header.FontWeight = System.Windows.FontWeights.Bold
            header.FontSize = 13
            header.Foreground = SolidColorBrush(Color.FromRgb(42, 125, 225))
            textblock.Inlines.Add(header)
            textblock.Inlines.Add(Run("\n"))
            
            # Add each source with icon and styling
            for source in sources:
                textblock.Inlines.Add(Run("\n"))
                
                # Bullet/icon
                bullet = Run("→ ")
                bullet.Foreground = SolidColorBrush(Color.FromRgb(42, 125, 225))
                bullet.FontWeight = System.Windows.FontWeights.Bold
                textblock.Inlines.Add(bullet)
                
                # Create hyperlink
                hyperlink = Hyperlink()
                hyperlink.Inlines.Add(Run(source['title']))
                hyperlink.NavigateUri = System.Uri(source['url'])
                hyperlink.RequestNavigate += self.on_hyperlink_click
                hyperlink.Foreground = SolidColorBrush(Color.FromRgb(42, 125, 225))
                hyperlink.TextDecorations = None  # Remove underline until hover
                
                textblock.Inlines.Add(hyperlink)
                
                # Add category if available
                if source.get('category'):
                    category_text = Run(" [{}]".format(source['category']))
                    category_text.FontSize = 10
                    category_text.Foreground = SolidColorBrush(Color.FromRgb(120, 120, 120))
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
            
            # Handle bold **text**
            if '**' in line:
                parts = re.split(r'(\*\*.*?\*\*)', line)
                for part in parts:
                    if part.startswith('**') and part.endswith('**'):
                        run = Run(part[2:-2])
                        run.FontWeight = System.Windows.FontWeights.Bold
                        textblock.Inlines.Add(run)
                    elif part:
                        textblock.Inlines.Add(Run(part))
            # Handle bullet points
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                textblock.Inlines.Add(Run("  " + line.strip()))
            # Handle numbered lists
            elif re.match(r'^\d+\.\s', line.strip()):
                textblock.Inlines.Add(Run("  " + line.strip()))
            # Handle headers (make bold and slightly larger)
            elif line.strip().startswith('#'):
                header_text = line.strip().lstrip('#').strip()
                run = Run("\n" + header_text + "\n")
                run.FontWeight = System.Windows.FontWeights.Bold
                run.FontSize = 15
                textblock.Inlines.Add(run)
            else:
                textblock.Inlines.Add(Run(line))
    
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
