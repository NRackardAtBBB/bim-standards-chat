
import os
import re

file_path = 'BBB.extension/lib/standards_chat/chat_window.py'
with open(file_path, 'r') as f:
    content = f.read()

# 1. Update _wrap_with_avatar to fix Assistant layout (fix text cutoff) and support generic content
# Replace the assistant column definition logic
old_assistant_layout = """        else:
            # Assistant: [avatar] [bubble] [flex space]
            col1 = ColumnDefinition()
            col1.Width = GridLength.Auto
            col2 = ColumnDefinition()
            col2.Width = GridLength.Auto
            col3 = ColumnDefinition()
            col3.Width = GridLength(1, GridUnitType.Star)
            container.ColumnDefinitions.Add(col1)
            container.ColumnDefinitions.Add(col2)
            container.ColumnDefinitions.Add(col3)

            avatar = self._create_bot_avatar()
            Grid.SetColumn(avatar, 0)
            Grid.SetColumn(bubble, 1)
            container.Children.Add(avatar)
            container.Children.Add(bubble)"""

new_assistant_layout = """        else:
            # Assistant: [avatar] [bubble/content]
            col1 = ColumnDefinition()
            col1.Width = GridLength.Auto
            col2 = ColumnDefinition()
            col2.Width = GridLength(1, GridUnitType.Star) # Take remaining space to allow wrapping
            container.ColumnDefinitions.Add(col1)
            container.ColumnDefinitions.Add(col2)

            avatar = self._create_bot_avatar()
            Grid.SetColumn(avatar, 0)
            
            # Align content to left but allow it to stretch if needed?
            # Actually for bubble we usually want it HorizontalAlignment.Left
            if hasattr(bubble, 'HorizontalAlignment'):
                bubble.HorizontalAlignment = HorizontalAlignment.Left
                
            Grid.SetColumn(bubble, 1)
            container.Children.Add(avatar)
            container.Children.Add(bubble)"""

content = content.replace(old_assistant_layout, new_assistant_layout)

# 2. Add _create_sources_panel helper method
sources_helper_code = """    def _create_sources_panel(self, sources):
        \"\"\"Create a separate panel for sources (displayed below bubble)\"\"\"
        if not sources:
            return None
            
        from System.Windows.Controls import StackPanel, WrapPanel
        
        panel = WrapPanel() 
        panel.Orientation = Orientation.Horizontal
        panel.Margin = Thickness(12, 4, 0, 8) # Indent slightly from bubble left
        
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
                sp_icon_bitmap.UriSource = Uri("file:///" + sp_icon_path.replace("\\\\", "/"))
                sp_icon_bitmap.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad
                sp_icon_bitmap.EndInit()
        except:
            pass

        for source in sources:
            # Create a pill/chip for each source
            source_border = Border()
            source_border.Background = SolidColorBrush(Color.FromRgb(0xF3, 0xF2, 0xF1))
            source_border.CornerRadius = System.Windows.CornerRadius(12)
            source_border.Padding = Thickness(8, 4, 8, 4)
            source_border.Margin = Thickness(0, 0, 8, 4)
            
            # Content stack for the chip
            chip_stack = StackPanel()
            chip_stack.Orientation = Orientation.Horizontal
            
            # Icon
            if sp_icon_bitmap:
                img = Image()
                img.Source = sp_icon_bitmap
                img.Width = 12
                img.Height = 12
                img.Margin = Thickness(0, 1, 6, 0)
                chip_stack.Children.Add(img)
            
            # Link Text
            # We use a Button styled as a link or just a clickable text
            # Creating a Hyperlink inside a TextBlock inside the chip
            
            tb = TextBlock()
            
            hyperlink = Hyperlink()
            link_run = Run(source['title'])
            link_run.FontSize = 11
            hyperlink.Inlines.Add(link_run)
            hyperlink.NavigateUri = System.Uri(source['url'])
            hyperlink.RequestNavigate += self.on_hyperlink_click
            hyperlink.Foreground = grey_brush
            hyperlink.TextDecorations = None
            
            tb.Inlines.Add(hyperlink)
            chip_stack.Children.Add(tb)
            
            source_border.Child = chip_stack
            panel.Children.Add(source_border)
            
        return panel
"""

# Insert _create_sources_panel before _add_sources_to_textblock
insert_pos = content.find("def _add_sources_to_textblock")
content = content[:insert_pos] + sources_helper_code + "\n    " + content[insert_pos:]

# 3. Update add_message to use _create_sources_panel and stack elements
add_message_old = """        # Add subdued source links
        if sources and not is_user:
            self._add_sources_to_textblock(textblock, sources)
        border.Child = textblock

        # Wrap with avatar and add to panel
        container = self._wrap_with_avatar(border, is_user)
        self.messages_panel.Children.Add(container)"""

add_message_new = """        border.Child = textblock

        # Prepare content element (either just border or stack with sources)
        content_element = border
        
        if sources and not is_user:
            # Create stack for bubble + sources
            stack = StackPanel()
            stack.Children.Add(border)
            
            sources_panel = self._create_sources_panel(sources)
            if sources_panel:
                stack.Children.Add(sources_panel)
            
            content_element = stack

        # Wrap with avatar and add to panel
        container = self._wrap_with_avatar(content_element, is_user)
        self.messages_panel.Children.Add(container)"""

content = content.replace(add_message_old, add_message_new)

# 4. Update start_streaming_response to use a StackPanel container
start_stream_old = """        # Create text content
        textblock = TextBlock()
        textblock.TextWrapping = TextWrapping.Wrap
        textblock.Foreground = self.FindResource("TextPrimaryColor")
        textblock.Name = "StreamingTextBlock"

        border.Child = textblock

        # Wrap with bot avatar
        container = self._wrap_with_avatar(border, is_user=False)
        self.messages_panel.Children.Add(container)

        # Store references
        self.streaming_textblock = textblock
        self.streaming_border = border"""

# We need to wrap border in a stackpanel so we can add sources later
start_stream_new = """        # Create text content
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
        self.streaming_content_stack = content_stack"""

content = content.replace(start_stream_old, start_stream_new)

# 5. Update finish_streaming_response to add sources to the stack
finish_stream_find = """                # Add subdued source links
                self._add_sources_to_textblock(self.streaming_textblock, sources)"""

finish_stream_replace = """                # Add subdued source links below bubble
                if sources:
                    sources_panel = self._create_sources_panel(sources)
                    if sources_panel and hasattr(self, 'streaming_content_stack'):
                        self.streaming_content_stack.Children.Add(sources_panel)"""

# Note: finish_streaming_response had a try/catch and variable cleanup. 
# We need to make sure we clean up new variables too.
content = content.replace(finish_stream_find, finish_stream_replace)

# Cleanup in finish_streaming_response
cleanup_old = """            self.streaming_textblock = None
            self.streaming_border = None
            self.streaming_text = u"" """
cleanup_new = """            self.streaming_textblock = None
            self.streaming_border = None
            self.streaming_content_stack = None
            self.streaming_text = u"" """
content = content.replace(cleanup_old, cleanup_new)

# Cleanup in exception handler too
content = content.replace("""            self.streaming_border = None
            self.streaming_text = u"" """, """            self.streaming_border = None
            self.streaming_content_stack = None
            self.streaming_text = u"" """)

with open(file_path, 'w') as f:
    f.write(content)
print("Updated chat_window.py")
