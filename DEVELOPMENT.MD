# Technical Specification: Revit Standards Assistant (PyRevit + Notion RAG + Claude)

## 1. Project Overview

### 1.1 Purpose
Develop a PyRevit plugin that provides an AI-powered chat interface within Autodesk Revit to help users query BBB's Revit standards documentation stored in Notion. The system uses Retrieval-Augmented Generation (RAG) to provide contextually relevant answers with source citations.

### 1.2 Goals
- Reduce time spent searching for standards documentation
- Provide consistent, accurate answers based on official BBB standards
- Make standards accessible without leaving Revit
- Track commonly asked questions to improve documentation
- Enable easy updates to standards by non-technical staff

### 1.3 Target Users
- 150+ Revit users across 5 BBB studios
- Architecture staff from junior designers to senior technical leaders
- BIM coordinators and managers

---

## 2. Technical Stack

### 2.1 Core Technologies
- **PyRevit**: 4.8.x or higher (IronPython 2.7.x)
- **Revit API**: 2023, 2024, 2025 compatibility required
- **Notion API**: v1 (2022-06-28)
- **Anthropic API**: Claude Sonnet 4.5 (claude-sonnet-4-20250514)
- **WPF**: For user interface
- **JSON**: For configuration and data serialization

### 2.2 Dependencies
```python
# Python packages (available in IronPython)
- System (WPF/XAML)
- clr (Common Language Runtime)
- json
- System.Net.Http (for API calls)

# External assemblies to reference
- PresentationFramework
- PresentationCore
- WindowsBase
- System.Xaml
```

---

## 3. System Architecture

### 3.1 Component Diagram
```
┌─────────────────────────────────────────────────────┐
│                    Revit User                        │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              PyRevit Chat Interface                  │
│  ┌──────────────────────────────────────────────┐   │
│  │  - Chat Window (WPF)                         │   │
│  │  - Message History Display                   │   │
│  │  - Input Box & Send Button                   │   │
│  │  - Loading Indicators                        │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│            Query Processing Module                   │
│  - Parse user input                                  │
│  - Extract Revit context (optional)                  │
│  - Format queries                                    │
└──────────────────────┬──────────────────────────────┘
                       │
           ┌───────────┴───────────┐
           ▼                       ▼
┌─────────────────────┐ ┌─────────────────────────────┐
│   Notion RAG Module │ │   Anthropic API Module      │
│                     │ │                             │
│  - Search Notion    │ │  - Format prompts           │
│  - Fetch pages      │ │  - Make API calls           │
│  - Extract content  │ │  - Parse responses          │
│  - Rank relevance   │ │  - Handle streaming         │
└──────────┬──────────┘ └─────────────┬───────────────┘
           │                          │
           └──────────┬───────────────┘
                      ▼
           ┌─────────────────────┐
           │  Response Formatter │
           │  - Add citations    │
           │  - Format links     │
           │  - Display result   │
           └─────────────────────┘
```

### 3.2 Data Flow
```
1. User enters question in chat window
2. System searches Notion for relevant standards pages (top 3-5 results)
3. System fetches full content from selected Notion pages
4. System constructs prompt with:
   - User question
   - Retrieved Notion content
   - Optional Revit context
5. System sends prompt to Claude API
6. Claude generates response with citations
7. System displays response with clickable Notion links
8. System logs interaction (optional analytics)
```

---

## 4. Notion Database Structure

### 4.1 Database Schema

**Database Name**: "BBB Revit Standards"

**Properties**:
```
┌─────────────────┬──────────────┬────────────────────────────┐
│ Property Name   │ Type         │ Options                    │
├─────────────────┼──────────────┼────────────────────────────┤
│ Title           │ Title        │ (Standard name)            │
│ Category        │ Select       │ - Modeling                 │
│                 │              │ - Worksets                 │
│                 │              │ - Views                    │
│                 │              │ - Families                 │
│                 │              │ - Documentation            │
│                 │              │ - Collaboration            │
│                 │              │ - Guardian Rules           │
│                 │              │ - General BIM              │
│ Studio          │ Multi-select │ - All Studios              │
│                 │              │ - Preservation             │
│                 │              │ - Museums & Culture        │
│                 │              │ - Civic & Urban            │
│                 │              │ - Higher Ed                │
│                 │              │ - Planning & Analysis      │
│ Revit Version   │ Multi-select │ - 2023, 2024, 2025         │
│ Status          │ Select       │ - Active                   │
│                 │              │ - Draft                    │
│                 │              │ - Under Review             │
│                 │              │ - Deprecated               │
│ Last Updated    │ Date         │                            │
│ Owner           │ Person       │                            │
│ Keywords        │ Multi-select │ (searchable tags)          │
│ Priority        │ Select       │ - Critical                 │
│                 │              │ - Important                │
│                 │              │ - Reference                │
└─────────────────┴──────────────┴────────────────────────────┘
```

### 4.2 Page Content Structure
Each standard page should follow this template:

```
# [Standard Title]

## Overview
Brief description of what this standard covers

## When to Use
Specific scenarios where this applies

## Requirements
- Bullet point requirements
- Clear, actionable items

## Examples
Visual examples, screenshots, or before/after images

## Common Issues
Problems people encounter and solutions

## Related Standards
Links to related Notion pages

## Guardian Rules
If applicable, which Guardian checks enforce this

## Last Updated
Date and change notes
```

### 4.3 Sample Standards to Create

**Initial pages to populate**:
1. Workset Naming Convention
2. Level Management Standards
3. View Template Usage
4. Family Placement Guidelines
5. Link Management Protocol
6. Sheet Organization
7. Phase Management
8. Design Options Best Practices
9. Guardian Error Resolution
10. ACC File Structure

---

## 5. PyRevit Extension Structure

### 5.1 File Organization
```
BBB.extension/
├── BBB.tab/
│   └── Standards Assistant.panel/
│       ├── Standards Chat.pushbutton/
│       │   ├── icon.png
│       │   ├── script.py
│       │   └── bundle.yaml
│       └── Settings.pushbutton/
│           ├── icon.png
│           ├── script.py
│           └── bundle.yaml
├── lib/
│   ├── standards_chat/
│   │   ├── __init__.py
│   │   ├── chat_window.py
│   │   ├── notion_client.py
│   │   ├── anthropic_client.py
│   │   ├── config_manager.py
│   │   └── utils.py
│   └── ui/
│       └── chat_window.xaml
└── config/
    ├── config.json
    └── api_keys.json  # Should be in .gitignore
```

### 5.2 Configuration Files

**config.json**:
```json
{
  "notion": {
    "database_id": "your-notion-database-id",
    "api_version": "2022-06-28",
    "max_search_results": 5,
    "cache_duration_minutes": 60
  },
  "anthropic": {
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 2048,
    "temperature": 0.7,
    "system_prompt": "You are a helpful Revit standards assistant for Beyer Blinder Belle..."
  },
  "ui": {
    "window_width": 500,
    "window_height": 700,
    "theme": "light"
  },
  "logging": {
    "enabled": true,
    "log_file": "standards_chat.log",
    "analytics_enabled": true
  }
}
```

**api_keys.json** (encrypted or secured):
```json
{
  "notion_api_key": "secret_xxxxx",
  "anthropic_api_key": "sk-ant-xxxxx"
}
```

---

## 6. Component Specifications

### 6.1 Main Script (script.py)

```python
"""
Standards Chat - Main Entry Point
Opens the chat interface for querying BBB Revit standards
"""

from pyrevit import script, forms
from standards_chat.chat_window import StandardsChatWindow

__title__ = "Standards\nChat"
__author__ = "BBB DCT Team"
__doc__ = "AI-powered assistant for BBB Revit standards"

def main():
    """Launch the standards chat window"""
    try:
        # Check if window is already open
        existing_window = script.get_window(StandardsChatWindow)
        if existing_window:
            existing_window.Activate()
        else:
            # Create and show new window
            chat_window = StandardsChatWindow()
            chat_window.Show()
            
    except Exception as e:
        forms.alert(
            "Failed to open Standards Chat:\n{}".format(str(e)),
            title="Error",
            warn_icon=True
        )

if __name__ == '__main__':
    main()
```

### 6.2 Chat Window UI (chat_window.xaml)

```xml
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="BBB Standards Assistant" 
        Height="700" Width="500"
        MinHeight="500" MinWidth="400"
        WindowStartupLocation="CenterScreen"
        Background="#F5F5F5">
    
    <Window.Resources>
        <!-- Styles -->
        <Style x:Key="MessageBubbleUser" TargetType="Border">
            <Setter Property="Background" Value="#0078D4"/>
            <Setter Property="CornerRadius" Value="8"/>
            <Setter Property="Padding" Value="12"/>
            <Setter Property="Margin" Value="50,5,10,5"/>
            <Setter Property="HorizontalAlignment" Value="Right"/>
        </Style>
        
        <Style x:Key="MessageBubbleAssistant" TargetType="Border">
            <Setter Property="Background" Value="White"/>
            <Setter Property="CornerRadius" Value="8"/>
            <Setter Property="Padding" Value="12"/>
            <Setter Property="Margin" Value="10,5,50,5"/>
            <Setter Property="HorizontalAlignment" Value="Left"/>
            <Setter Property="BorderBrush" Value="#E0E0E0"/>
            <Setter Property="BorderThickness" Value="1"/>
        </Style>
    </Window.Resources>
    
    <Grid>
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>  <!-- Header -->
            <RowDefinition Height="*"/>     <!-- Messages -->
            <RowDefinition Height="Auto"/>  <!-- Input -->
        </Grid.RowDefinitions>
        
        <!-- Header -->
        <Border Grid.Row="0" Background="#0078D4" Padding="15,10">
            <StackPanel>
                <TextBlock Text="BBB Standards Assistant" 
                          FontSize="18" 
                          FontWeight="Bold" 
                          Foreground="White"/>
                <TextBlock x:Name="StatusText" 
                          Text="Ready" 
                          FontSize="11" 
                          Foreground="#E0E0E0"
                          Margin="0,3,0,0"/>
            </StackPanel>
        </Border>
        
        <!-- Messages Area -->
        <ScrollViewer Grid.Row="1" 
                     x:Name="MessageScrollViewer"
                     VerticalScrollBarVisibility="Auto"
                     Padding="10">
            <StackPanel x:Name="MessagesPanel">
                <!-- Welcome message -->
                <Border Style="{StaticResource MessageBubbleAssistant}">
                    <TextBlock TextWrapping="Wrap" Foreground="#333">
                        <Run Text="👋 Hi! I'm here to help you with BBB's Revit standards."/>
                        <LineBreak/>
                        <LineBreak/>
                        <Run Text="Ask me anything about:"/>
                        <LineBreak/>
                        <Run Text="• Modeling standards"/>
                        <LineBreak/>
                        <Run Text="• Workset organization"/>
                        <LineBreak/>
                        <Run Text="• View templates"/>
                        <LineBreak/>
                        <Run Text="• Family guidelines"/>
                        <LineBreak/>
                        <Run Text="• Guardian rules"/>
                        <LineBreak/>
                        <LineBreak/>
                        <Run Text="I'll search our standards and provide detailed answers with links to the full documentation."/>
                    </TextBlock>
                </Border>
            </StackPanel>
        </ScrollViewer>
        
        <!-- Input Area -->
        <Border Grid.Row="2" 
                Background="White" 
                BorderBrush="#E0E0E0" 
                BorderThickness="0,1,0,0"
                Padding="10">
            <Grid>
                <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="Auto"/>
                </Grid.ColumnDefinitions>
                
                <TextBox x:Name="InputTextBox" 
                        Grid.Column="0"
                        TextWrapping="Wrap"
                        AcceptsReturn="True"
                        MaxHeight="100"
                        VerticalScrollBarVisibility="Auto"
                        Padding="10"
                        FontSize="13"
                        BorderBrush="#E0E0E0"
                        BorderThickness="1"/>
                
                <Button x:Name="SendButton" 
                       Grid.Column="1"
                       Content="Send"
                       Width="80"
                       Height="36"
                       Margin="10,0,0,0"
                       Background="#0078D4"
                       Foreground="White"
                       FontWeight="Bold"
                       BorderThickness="0"
                       Cursor="Hand"/>
            </Grid>
        </Border>
        
        <!-- Loading Overlay -->
        <Grid x:Name="LoadingOverlay" 
              Grid.RowSpan="3" 
              Background="#80000000" 
              Visibility="Collapsed">
            <Border Background="White" 
                   Padding="20" 
                   CornerRadius="8"
                   HorizontalAlignment="Center"
                   VerticalAlignment="Center">
                <StackPanel>
                    <TextBlock Text="🤔 Thinking..." 
                              FontSize="16" 
                              HorizontalAlignment="Center"/>
                    <TextBlock x:Name="LoadingStatusText" 
                              Text="Searching standards..." 
                              FontSize="12" 
                              Foreground="#666"
                              Margin="0,10,0,0"
                              HorizontalAlignment="Center"/>
                </StackPanel>
            </Border>
        </Grid>
    </Grid>
</Window>
```

### 6.3 Chat Window Controller (chat_window.py)

```python
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
from System.Windows.Controls import TextBlock, Border, ScrollViewer
from System.Windows.Documents import Run, Hyperlink
from System.Windows.Media import Brushes, SolidColorBrush
from System.Windows import Thickness, TextWrapping, HorizontalAlignment
from System.Threading import Thread, ThreadStart
from System.Windows.Threading import Dispatcher
import os
import sys

# Add lib path
script_dir = os.path.dirname(__file__)
lib_path = os.path.join(os.path.dirname(script_dir), 'lib')
if lib_path not in sys.path:
    sys.path.append(lib_path)

from standards_chat.notion_client import NotionClient
from standards_chat.anthropic_client import AnthropicClient
from standards_chat.config_manager import ConfigManager
from standards_chat.utils import extract_revit_context


class StandardsChatWindow(Window):
    """Main chat window for standards assistant"""
    
    def __init__(self):
        """Initialize the chat window"""
        # Load XAML
        xaml_path = os.path.join(
            os.path.dirname(__file__),
            '../ui/chat_window.xaml'
        )
        with open(xaml_path, 'r') as f:
            self.xaml = f.read()
        
        # Parse XAML
        window = XamlReader.Parse(self.xaml)
        
        # Copy properties from parsed window
        self.Title = window.Title
        self.Height = window.Height
        self.Width = window.Width
        self.Content = window.Content
        
        # Get UI elements
        self.messages_panel = self.FindName('MessagesPanel')
        self.input_textbox = self.FindName('InputTextBox')
        self.send_button = self.FindName('SendButton')
        self.status_text = self.FindName('StatusText')
        self.loading_overlay = self.FindName('LoadingOverlay')
        self.loading_status_text = self.FindName('LoadingStatusText')
        self.message_scrollviewer = self.FindName('MessageScrollViewer')
        
        # Initialize clients
        self.config = ConfigManager()
        self.notion = NotionClient(self.config)
        self.anthropic = AnthropicClient(self.config)
        
        # Conversation history
        self.conversation = []
        
        # Wire up events
        self.send_button.Click += self.on_send_click
        self.input_textbox.KeyDown += self.on_input_keydown
        
        # Focus input box
        self.input_textbox.Focus()
    
    def on_send_click(self, sender, args):
        """Handle send button click"""
        self.send_message()
    
    def on_input_keydown(self, sender, args):
        """Handle keyboard input (Ctrl+Enter to send)"""
        if args.Key == System.Windows.Input.Key.Enter:
            if System.Windows.Input.Keyboard.Modifiers == \
               System.Windows.Input.ModifierKeys.Control:
                self.send_message()
                args.Handled = True
    
    def send_message(self):
        """Send user message and get response"""
        user_input = self.input_textbox.Text.strip()
        
        if not user_input:
            return
        
        # Clear input
        self.input_textbox.Clear()
        
        # Add user message to UI
        self.add_message(user_input, is_user=True)
        
        # Show loading
        self.show_loading("Searching standards...")
        
        # Process in background thread
        def process_query():
            try:
                # Update status
                self.update_loading_status("Searching Notion database...")
                
                # Search Notion for relevant standards
                relevant_pages = self.notion.search_standards(user_input)
                
                # Extract Revit context if available
                revit_context = extract_revit_context()
                
                # Update status
                self.update_loading_status("Generating response...")
                
                # Get response from Claude
                response = self.anthropic.get_response(
                    user_query=user_input,
                    notion_pages=relevant_pages,
                    revit_context=revit_context,
                    conversation_history=self.conversation
                )
                
                # Update conversation history
                self.conversation.append({
                    'user': user_input,
                    'assistant': response['text'],
                    'sources': response['sources']
                })
                
                # Add assistant message to UI
                self.Dispatcher.Invoke(
                    lambda: self.add_message(
                        response['text'],
                        is_user=False,
                        sources=response['sources']
                    )
                )
                
            except Exception as e:
                error_msg = "Sorry, I encountered an error: {}".format(str(e))
                self.Dispatcher.Invoke(
                    lambda: self.add_message(error_msg, is_user=False)
                )
            
            finally:
                # Hide loading
                self.Dispatcher.Invoke(self.hide_loading)
        
        # Start background thread
        thread = Thread(ThreadStart(process_query))
        thread.IsBackground = True
        thread.Start()
    
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
            border.Background = SolidColorBrush.FromRgb(0, 120, 212)  # Blue
            text_color = Brushes.White
        else:
            border.Background = Brushes.White
            border.BorderBrush = SolidColorBrush.FromRgb(224, 224, 224)
            border.BorderThickness = Thickness(1)
            text_color = SolidColorBrush.FromRgb(51, 51, 51)
        
        # Create text content
        textblock = TextBlock()
        textblock.TextWrapping = TextWrapping.Wrap
        textblock.Foreground = text_color
        textblock.Inlines.Add(Run(text))
        
        # Add sources if present
        if sources and not is_user:
            textblock.Inlines.Add(Run("\n\n📚 Sources:\n"))
            for source in sources:
                # Create hyperlink
                hyperlink = Hyperlink()
                hyperlink.Inlines.Add(Run("• " + source['title']))
                hyperlink.NavigateUri = System.Uri(source['url'])
                hyperlink.RequestNavigate += self.on_hyperlink_click
                hyperlink.Foreground = SolidColorBrush.FromRgb(0, 120, 212)
                
                textblock.Inlines.Add(hyperlink)
                textblock.Inlines.Add(Run("\n"))
        
        border.Child = textblock
        
        # Add to panel
        self.messages_panel.Children.Add(border)
        
        # Scroll to bottom
        self.message_scrollviewer.ScrollToBottom()
    
    def on_hyperlink_click(self, sender, args):
        """Open hyperlink in browser"""
        import webbrowser
        webbrowser.open(str(args.Uri))
        args.Handled = True
    
    def show_loading(self, status="Loading..."):
        """Show loading overlay"""
        self.loading_overlay.Visibility = System.Windows.Visibility.Visible
        self.loading_status_text.Text = status
        self.send_button.IsEnabled = False
        self.input_textbox.IsEnabled = False
    
    def hide_loading(self):
        """Hide loading overlay"""
        self.loading_overlay.Visibility = System.Windows.Visibility.Collapsed
        self.send_button.IsEnabled = True
        self.input_textbox.IsEnabled = True
        self.input_textbox.Focus()
    
    def update_loading_status(self, status):
        """Update loading status text"""
        self.Dispatcher.Invoke(
            lambda: setattr(self.loading_status_text, 'Text', status)
        )
```

### 6.4 Notion Client (notion_client.py)

```python
"""
Notion API Client
Handles all interactions with Notion API
"""

import json
import clr
clr.AddReference('System.Net.Http')

from System.Net.Http import HttpClient, HttpRequestMessage, HttpMethod
from System.Net.Http.Headers import MediaTypeWithQualityHeaderValue
from System.Text import Encoding


class NotionClient:
    """Client for interacting with Notion API"""
    
    def __init__(self, config):
        """Initialize Notion client"""
        self.config = config
        self.api_key = config.get_api_key('notion')
        self.database_id = config.get('notion', 'database_id')
        self.api_version = config.get('notion', 'api_version')
        self.base_url = "https://api.notion.com/v1"
        
        # Create HTTP client
        self.client = HttpClient()
        self.client.DefaultRequestHeaders.Add(
            "Authorization", 
            "Bearer {}".format(self.api_key)
        )
        self.client.DefaultRequestHeaders.Add(
            "Notion-Version", 
            self.api_version
        )
        self.client.DefaultRequestHeaders.Accept.Add(
            MediaTypeWithQualityHeaderValue("application/json")
        )
    
    def search_standards(self, query, max_results=5):
        """
        Search Notion database for relevant standards
        
        Args:
            query (str): Search query
            max_results (int): Maximum number of results to return
            
        Returns:
            list: List of relevant page dictionaries with content
        """
        # Search Notion
        search_results = self._search_pages(query)
        
        # Filter to only Active status pages from standards database
        relevant_pages = []
        for result in search_results[:max_results]:
            try:
                # Check if page is from standards database
                if self._is_standards_page(result):
                    # Fetch full page content
                    page_content = self._fetch_page_content(result['id'])
                    
                    # Extract metadata
                    page_data = {
                        'id': result['id'],
                        'title': self._extract_title(result),
                        'url': result['url'],
                        'content': page_content,
                        'category': self._extract_property(result, 'Category'),
                        'last_updated': self._extract_property(result, 'Last Updated')
                    }
                    
                    relevant_pages.append(page_data)
                    
            except Exception as e:
                # Log error but continue with other pages
                print("Error processing page {}: {}".format(
                    result.get('id', 'unknown'), 
                    str(e)
                ))
                continue
        
        return relevant_pages
    
    def _search_pages(self, query):
        """Execute search against Notion API"""
        url = "{}/search".format(self.base_url)
        
        payload = {
            "query": query,
            "filter": {
                "value": "page",
                "property": "object"
            },
            "sort": {
                "direction": "descending",
                "timestamp": "last_edited_time"
            },
            "page_size": 10
        }
        
        request = HttpRequestMessage(HttpMethod.Post, url)
        request.Content = System.Net.Http.StringContent(
            json.dumps(payload),
            Encoding.UTF8,
            "application/json"
        )
        
        response = self.client.SendAsync(request).Result
        response.EnsureSuccessStatusCode()
        
        content = response.Content.ReadAsStringAsync().Result
        data = json.loads(content)
        
        return data.get('results', [])
    
    def _fetch_page_content(self, page_id):
        """Fetch full content of a Notion page"""
        url = "{}/blocks/{}/children".format(self.base_url, page_id)
        
        request = HttpRequestMessage(HttpMethod.Get, url)
        response = self.client.SendAsync(request).Result
        response.EnsureSuccessStatusCode()
        
        content = response.Content.ReadAsStringAsync().Result
        data = json.loads(content)
        
        blocks = data.get('results', [])
        
        # Convert blocks to text
        text_content = self._blocks_to_text(blocks)
        
        return text_content
    
    def _blocks_to_text(self, blocks):
        """Convert Notion blocks to plain text"""
        text_parts = []
        
        for block in blocks:
            block_type = block.get('type')
            
            if block_type == 'paragraph':
                text = self._extract_rich_text(block['paragraph'])
                if text:
                    text_parts.append(text)
            
            elif block_type == 'heading_1':
                text = self._extract_rich_text(block['heading_1'])
                if text:
                    text_parts.append("\n## {}".format(text))
            
            elif block_type == 'heading_2':
                text = self._extract_rich_text(block['heading_2'])
                if text:
                    text_parts.append("\n### {}".format(text))
            
            elif block_type == 'heading_3':
                text = self._extract_rich_text(block['heading_3'])
                if text:
                    text_parts.append("\n#### {}".format(text))
            
            elif block_type == 'bulleted_list_item':
                text = self._extract_rich_text(block['bulleted_list_item'])
                if text:
                    text_parts.append("• {}".format(text))
            
            elif block_type == 'numbered_list_item':
                text = self._extract_rich_text(block['numbered_list_item'])
                if text:
                    text_parts.append("- {}".format(text))
            
            elif block_type == 'code':
                text = self._extract_rich_text(block['code'])
                if text:
                    text_parts.append("\n```\n{}\n```".format(text))
            
            elif block_type == 'quote':
                text = self._extract_rich_text(block['quote'])
                if text:
                    text_parts.append("> {}".format(text))
        
        return "\n".join(text_parts)
    
    def _extract_rich_text(self, block_content):
        """Extract plain text from rich text array"""
        rich_text = block_content.get('rich_text', [])
        return ''.join([rt.get('plain_text', '') for rt in rich_text])
    
    def _is_standards_page(self, page):
        """Check if page belongs to standards database"""
        # Check if page has parent database matching standards DB
        parent = page.get('parent', {})
        if parent.get('type') == 'database_id':
            return parent.get('database_id') == self.database_id
        return False
    
    def _extract_title(self, page):
        """Extract title from page properties"""
        try:
            properties = page.get('properties', {})
            title_prop = properties.get('title', {}) or properties.get('Name', {})
            title_array = title_prop.get('title', [])
            if title_array:
                return title_array[0].get('plain_text', 'Untitled')
        except:
            pass
        return 'Untitled'
    
    def _extract_property(self, page, prop_name):
        """Extract property value from page"""
        try:
            properties = page.get('properties', {})
            prop = properties.get(prop_name, {})
            prop_type = prop.get('type')
            
            if prop_type == 'select':
                return prop['select'].get('name')
            elif prop_type == 'date':
                return prop['date'].get('start')
            elif prop_type == 'multi_select':
                return [item['name'] for item in prop['multi_select']]
            
        except:
            pass
        return None
```

### 6.5 Anthropic Client (anthropic_client.py)

```python
"""
Anthropic API Client
Handles all interactions with Claude API
"""

import json
import clr
clr.AddReference('System.Net.Http')

from System.Net.Http import HttpClient, HttpRequestMessage, HttpMethod
from System.Net.Http.Headers import MediaTypeWithQualityHeaderValue
from System.Text import Encoding


class AnthropicClient:
    """Client for interacting with Anthropic API"""
    
    def __init__(self, config):
        """Initialize Anthropic client"""
        self.config = config
        self.api_key = config.get_api_key('anthropic')
        self.model = config.get('anthropic', 'model')
        self.max_tokens = config.get('anthropic', 'max_tokens')
        self.temperature = config.get('anthropic', 'temperature')
        self.system_prompt = config.get('anthropic', 'system_prompt')
        self.base_url = "https://api.anthropic.com/v1"
        
        # Create HTTP client
        self.client = HttpClient()
        self.client.DefaultRequestHeaders.Add(
            "x-api-key",
            self.api_key
        )
        self.client.DefaultRequestHeaders.Add(
            "anthropic-version",
            "2023-06-01"
        )
        self.client.DefaultRequestHeaders.Accept.Add(
            MediaTypeWithQualityHeaderValue("application/json")
        )
    
    def get_response(self, user_query, notion_pages, revit_context=None, 
                     conversation_history=None):
        """
        Get response from Claude with RAG context
        
        Args:
            user_query (str): User's question
            notion_pages (list): Relevant Notion pages
            revit_context (dict): Optional Revit context
            conversation_history (list): Previous conversation
            
        Returns:
            dict: Response with text and sources
        """
        # Build context from Notion pages
        context = self._build_context(notion_pages, revit_context)
        
        # Build messages array
        messages = self._build_messages(
            user_query, 
            context, 
            conversation_history
        )
        
        # Make API call
        response_data = self._call_api(messages)
        
        # Extract response
        response_text = response_data['content'][0]['text']
        
        # Format sources
        sources = [
            {
                'title': page['title'],
                'url': page['url'],
                'category': page.get('category', 'General')
            }
            for page in notion_pages
        ]
        
        return {
            'text': response_text,
            'sources': sources
        }
    
    def _build_context(self, notion_pages, revit_context):
        """Build context string from Notion pages and Revit info"""
        context_parts = []
        
        # Add Notion standards
        if notion_pages:
            context_parts.append("# Relevant BBB Standards\n")
            for i, page in enumerate(notion_pages, 1):
                context_parts.append(
                    "## Standard {}: {}\n".format(i, page['title'])
                )
                context_parts.append(
                    "Source: {}\n".format(page['url'])
                )
                if page.get('category'):
                    context_parts.append(
                        "Category: {}\n".format(page['category'])
                    )
                context_parts.append("\n{}\n\n".format(page['content']))
        
        # Add Revit context if available
        if revit_context:
            context_parts.append("\n# Current Revit Context\n")
            for key, value in revit_context.items():
                context_parts.append("- {}: {}\n".format(key, value))
        
        return ''.join(context_parts)
    
    def _build_messages(self, user_query, context, conversation_history):
        """Build messages array for API call"""
        messages = []
        
        # Add conversation history if present (last 3 exchanges)
        if conversation_history:
            recent_history = conversation_history[-3:]
            for exchange in recent_history:
                messages.append({
                    "role": "user",
                    "content": exchange['user']
                })
                messages.append({
                    "role": "assistant",
                    "content": exchange['assistant']
                })
        
        # Build current user message with context
        user_content = """{}

User Question: {}

Please provide a helpful, detailed answer based on BBB's standards documentation above. 
When referencing specific standards, mention them by name.
If multiple standards are relevant, explain how they work together.
If the standards don't fully address the question, acknowledge this and provide your best guidance.""".format(
            context,
            user_query
        )
        
        messages.append({
            "role": "user",
            "content": user_content
        })
        
        return messages
    
    def _call_api(self, messages):
        """Make API call to Claude"""
        url = "{}/messages".format(self.base_url)
        
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": self.system_prompt,
            "messages": messages
        }
        
        request = HttpRequestMessage(HttpMethod.Post, url)
        request.Content = System.Net.Http.StringContent(
            json.dumps(payload),
            Encoding.UTF8,
            "application/json"
        )
        
        response = self.client.SendAsync(request).Result
        
        # Check for errors
        if not response.IsSuccessStatusCode:
            error_content = response.Content.ReadAsStringAsync().Result
            raise Exception(
                "API Error ({}): {}".format(
                    response.StatusCode,
                    error_content
                )
            )
        
        content = response.Content.ReadAsStringAsync().Result
        data = json.loads(content)
        
        return data
```

### 6.6 Config Manager (config_manager.py)

```python
"""
Configuration Manager
Handles loading and accessing configuration
"""

import os
import json


class ConfigManager:
    """Manages configuration and API keys"""
    
    def __init__(self):
        """Initialize config manager"""
        # Get extension directory
        self.extension_dir = self._get_extension_dir()
        self.config_dir = os.path.join(self.extension_dir, 'config')
        
        # Load configuration files
        self.config = self._load_json('config.json')
        self.api_keys = self._load_json('api_keys.json')
    
    def _get_extension_dir(self):
        """Get the extension directory path"""
        # Navigate up from lib/standards_chat to extension root
        current_file = __file__
        lib_dir = os.path.dirname(os.path.dirname(current_file))
        extension_dir = os.path.dirname(lib_dir)
        return extension_dir
    
    def _load_json(self, filename):
        """Load JSON file from config directory"""
        filepath = os.path.join(self.config_dir, filename)
        
        if not os.path.exists(filepath):
            raise Exception(
                "Configuration file not found: {}".format(filepath)
            )
        
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def get(self, section, key, default=None):
        """Get configuration value"""
        try:
            return self.config[section][key]
        except KeyError:
            return default
    
    def get_api_key(self, service):
        """Get API key for a service"""
        key_name = "{}_api_key".format(service)
        
        if key_name not in self.api_keys:
            raise Exception(
                "API key for '{}' not found in api_keys.json".format(service)
            )
        
        api_key = self.api_keys[key_name]
        
        if not api_key or api_key.startswith('your-') or api_key.startswith('sk-ant-xxx'):
            raise Exception(
                "Please configure valid API key for '{}' in api_keys.json".format(service)
            )
        
        return api_key
```

### 6.7 Utilities (utils.py)

```python
"""
Utility Functions
Helper functions for extracting context and formatting
"""

try:
    from Autodesk.Revit.DB import *
    from Autodesk.Revit.UI import *
    REVIT_AVAILABLE = True
except ImportError:
    REVIT_AVAILABLE = False

from pyrevit import revit, DB


def extract_revit_context():
    """
    Extract relevant context from current Revit session
    
    Returns:
        dict: Dictionary of context information
    """
    if not REVIT_AVAILABLE:
        return None
    
    try:
        doc = revit.doc
        uidoc = revit.uidoc
        active_view = revit.active_view
        
        context = {}
        
        # Document info
        if doc:
            context['project_name'] = doc.Title or 'Untitled'
            context['revit_version'] = doc.Application.VersionNumber
            
        # Active view info
        if active_view:
            context['active_view'] = active_view.Name
            context['view_type'] = active_view.ViewType.ToString()
            
            # View template if any
            view_template_id = active_view.ViewTemplateId
            if view_template_id != DB.ElementId.InvalidElementId:
                template = doc.GetElement(view_template_id)
                if template:
                    context['view_template'] = template.Name
        
        # Current workset if applicable
        if doc.IsWorkshared:
            try:
                active_workset = doc.GetWorksetTable().GetActiveWorksetId()
                workset = doc.GetWorksetTable().GetWorkset(active_workset)
                context['active_workset'] = workset.Name
            except:
                pass
        
        # Selection info
        if uidoc:
            selection = uidoc.Selection
            selected_ids = selection.GetElementIds()
            
            if selected_ids.Count > 0:
                context['selection_count'] = selected_ids.Count
                
                # Get category of first selected element
                first_elem = doc.GetElement(list(selected_ids)[0])
                if first_elem and first_elem.Category:
                    context['selected_category'] = first_elem.Category.Name
        
        return context if context else None
        
    except Exception as e:
        # If any error extracting context, return None
        print("Error extracting Revit context: {}".format(str(e)))
        return None


def format_markdown(text):
    """
    Format markdown-style text for WPF display
    (Basic implementation - can be enhanced)
    """
    # This is a placeholder - would need more robust markdown parsing
    # For now, just return the text as-is
    return text


def truncate_text(text, max_length=500):
    """Truncate text to max length with ellipsis"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + "..."


def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename
```

---

## 7. System Prompt for Claude

The system prompt defines Claude's behavior as a standards assistant:

```
You are a helpful Revit standards assistant for Beyer Blinder Belle (BBB), an architecture firm with 150+ Revit users across 5 studios.

Your role is to help users understand and apply BBB's Revit standards by:
1. Answering questions clearly and accurately based on the provided standards documentation
2. Providing specific guidance relevant to their situation
3. Citing sources by referencing the standard names (e.g., "According to our Workset Naming Convention standard...")
4. Explaining the reasoning behind standards when helpful
5. Acknowledging when standards don't fully address a question
6. Being concise but thorough - aim for clarity over brevity

Communication style:
- Professional but friendly and approachable
- Use technical Revit terminology accurately
- Break down complex topics into clear steps
- Provide examples when helpful
- Don't over-explain obvious concepts to experienced users

When Revit context is provided (active view, workset, selection, etc.):
- Consider this context in your answers
- Provide more targeted guidance based on what they're currently working on
- Point out potential issues with their current setup if relevant

If multiple standards apply:
- Explain how they work together
- Prioritize the most relevant standard first
- Note any potential conflicts or special considerations

If the provided standards don't fully address the question:
- Acknowledge this clearly
- Provide your best guidance based on general Revit best practices
- Suggest related standards that might be helpful
- Recommend they consult with their studio BIM coordinator for clarification

Remember: You're representing BBB's standards, so maintain accuracy and consistency with the documentation provided.
```

---

## 8. Error Handling

### 8.1 API Error Scenarios

**Notion API Errors**:
```python
# Connection errors
- Network timeout (30 seconds)
- Invalid API key
- Rate limiting (3 requests per second)
- Database not found
- Insufficient permissions

# Handling
try:
    results = notion.search_standards(query)
except NotionAPIException as e:
    if e.status_code == 401:
        show_error("Authentication error. Please check Notion API key.")
    elif e.status_code == 429:
        show_error("Too many requests. Please wait a moment and try again.")
    elif e.status_code == 404:
        show_error("Standards database not found. Please contact DCT team.")
    else:
        show_error("Error searching standards: " + str(e))
```

**Anthropic API Errors**:
```python
# API errors
- Invalid API key
- Rate limiting
- Model overloaded
- Invalid request format
- Token limit exceeded

# Handling
try:
    response = anthropic.get_response(...)
except AnthropicAPIException as e:
    if e.status_code == 401:
        show_error("Authentication error. Please check Anthropic API key.")
    elif e.status_code == 429:
        show_error("Rate limit reached. Please try again in a moment.")
    elif e.status_code == 529:
        show_error("Claude is temporarily overloaded. Please try again shortly.")
    else:
        show_error("Error getting response: " + str(e))
```

### 8.2 User-Facing Error Messages

Keep errors informative but non-technical:

```python
ERROR_MESSAGES = {
    'no_api_key': "⚠️ Configuration required\n\nPlease contact your BIM coordinator to set up API keys.",
    
    'no_results': "🔍 No standards found\n\nI couldn't find any standards matching your query. Try rephrasing your question or contact your studio BIM coordinator.",
    
    'network_error': "📡 Connection issue\n\nUnable to reach the standards database. Please check your internet connection.",
    
    'rate_limit': "⏱️ Too many requests\n\nPlease wait a moment before trying again.",
    
    'general_error': "❌ Something went wrong\n\nPlease try again or contact the DCT team if the problem persists."
}
```

---

## 9. Security & Best Practices

### 9.1 API Key Management

**Storage**:
- Store API keys in `api_keys.json` (excluded from version control)
- Use environment variables as alternative
- Consider encryption for production deployment
- Restrict file permissions to administrators only

**Access Control**:
```python
# api_keys.json should have restricted permissions
# Windows: Only SYSTEM and Administrators can read
# Stored in: %APPDATA%\pyRevit\Extensions\BBB.extension\config\

# Alternative: Use Windows Credential Manager
import clr
clr.AddReference('System.Security')
from System.Security.Cryptography import ProtectedData

def store_api_key(service, key):
    """Store API key encrypted in Windows Credential Manager"""
    # Implementation using Windows Data Protection API
    pass
```

### 9.2 Rate Limiting

Implement client-side rate limiting to avoid API quota issues:

```python
import time
from collections import deque

class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, max_calls, time_window):
        """
        Args:
            max_calls: Maximum number of calls in time window
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = deque()
    
    def can_make_call(self):
        """Check if a call can be made"""
        now = time.time()
        
        # Remove old calls outside time window
        while self.calls and self.calls[0] < now - self.time_window:
            self.calls.popleft()
        
        # Check if under limit
        return len(self.calls) < self.max_calls
    
    def record_call(self):
        """Record that a call was made"""
        self.calls.append(time.time())
    
    def wait_if_needed(self):
        """Wait if rate limit reached"""
        if not self.can_make_call():
            wait_time = self.time_window - (time.time() - self.calls[0])
            if wait_time > 0:
                time.sleep(wait_time + 0.1)

# Usage
notion_limiter = RateLimiter(max_calls=3, time_window=1.0)  # 3 calls per second
anthropic_limiter = RateLimiter(max_calls=50, time_window=60.0)  # 50 per minute
```

### 9.3 Input Validation

Sanitize user inputs before API calls:

```python
def validate_user_input(text):
    """Validate and sanitize user input"""
    # Remove excessive whitespace
    text = ' '.join(text.split())
    
    # Limit length
    max_length = 2000
    if len(text) > max_length:
        text = text[:max_length]
    
    # Check for suspicious patterns
    suspicious_patterns = [
        'javascript:',
        '<script',
        'eval(',
        'onclick='
    ]
    
    text_lower = text.lower()
    for pattern in suspicious_patterns:
        if pattern in text_lower:
            raise ValueError("Invalid input detected")
    
    return text
```

---

## 10. Logging & Analytics

### 10.1 Usage Logging

Track usage for improving documentation:

```python
import json
import os
from datetime import datetime

class UsageLogger:
    """Log chat interactions for analytics"""
    
    def __init__(self, log_dir):
        self.log_dir = log_dir
        self.log_file = os.path.join(log_dir, 'usage.jsonl')
        
        # Create log directory if needed
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
    
    def log_interaction(self, query, response_sources, revit_context=None):
        """Log a single interaction"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'query': query,
            'sources_count': len(response_sources),
            'source_categories': [s.get('category') for s in response_sources],
            'revit_context': revit_context
        }
        
        # Append to log file (JSONL format)
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def get_popular_queries(self, limit=10):
        """Get most common query topics"""
        # Implementation for analytics dashboard
        pass
```

### 10.2 Error Logging

Log errors for troubleshooting:

```python
import traceback
import logging

# Configure logging
log_file = os.path.join(extension_dir, 'logs', 'errors.log')
logging.basicConfig(
    filename=log_file,
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def log_error(error, context=None):
    """Log error with context"""
    logging.error(
        "Error: {}\nContext: {}\nTraceback: {}".format(
            str(error),
            json.dumps(context) if context else 'None',
            traceback.format_exc()
        )
    )
```

---

## 11. Testing Plan

### 11.1 Unit Tests

Test individual components in isolation:

```python
# Test Notion client
def test_notion_search():
    notion = NotionClient(test_config)
    results = notion.search_standards("workset naming")
    assert len(results) > 0
    assert 'title' in results[0]
    assert 'url' in results[0]
    assert 'content' in results[0]

# Test Anthropic client
def test_anthropic_response():
    anthropic = AnthropicClient(test_config)
    response = anthropic.get_response(
        user_query="How should I name worksets?",
        notion_pages=[sample_page],
        revit_context=None,
        conversation_history=None
    )
    assert 'text' in response
    assert 'sources' in response
    assert len(response['text']) > 0
```

### 11.2 Integration Tests

Test full workflow:

```python
def test_full_query_workflow():
    """Test complete query from user input to response"""
    # Initialize components
    config = ConfigManager()
    notion = NotionClient(config)
    anthropic = AnthropicClient(config)
    
    # Execute query
    query = "What's the standard for naming worksets?"
    
    # Search Notion
    pages = notion.search_standards(query)
    assert len(pages) > 0
    
    # Get response
    response = anthropic.get_response(
        user_query=query,
        notion_pages=pages,
        revit_context=None,
        conversation_history=None
    )
    
    # Verify response
    assert 'workset' in response['text'].lower()
    assert len(response['sources']) > 0
```

### 11.3 UI Tests

Test user interface components:

```python
def test_chat_window_creation():
    """Test chat window can be created"""
    window = StandardsChatWindow()
    assert window is not None
    assert window.messages_panel is not None
    assert window.input_textbox is not None
    window.Close()

def test_add_message():
    """Test adding messages to chat"""
    window = StandardsChatWindow()
    
    # Add user message
    window.add_message("Test user message", is_user=True)
    assert window.messages_panel.Children.Count > 1  # Welcome + new message
    
    # Add assistant message with sources
    sources = [{'title': 'Test Standard', 'url': 'https://notion.so/test'}]
    window.add_message("Test assistant message", is_user=False, sources=sources)
    assert window.messages_panel.Children.Count > 2
    
    window.Close()
```

### 11.4 User Acceptance Testing

**Test Scenarios**:

1. **Basic Query**
   - User asks: "How should I name worksets?"
   - Expected: Relevant answer with link to Workset Naming standard

2. **Complex Query**
   - User asks: "I'm working on a museum project in the Preservation studio. What view templates should I use for sections?"
   - Expected: Answer considers studio context and links multiple standards

3. **Ambiguous Query**
   - User asks: "What about families?"
   - Expected: Claude asks for clarification or provides overview

4. **No Standards Found**
   - User asks: "How do I make coffee in Revit?"
   - Expected: Polite message that no standards cover this

5. **Context-Aware Query**
   - User asks "Is this workset name okay?" while in Revit with active workset
   - Expected: Answer references their current workset name

---

## 12. Deployment

### 12.1 Pre-Deployment Checklist

```
□ Notion database created and populated with standards
□ Notion integration created and API key obtained
□ Anthropic API key obtained
□ PyRevit extension structure created
□ All Python files implemented
□ XAML UI file created
□ Configuration files set up
□ API keys configured (not in git)
□ Icons created (24x24 PNG)
□ Bundle.yaml files configured
□ Initial testing completed
□ Documentation written
□ User guide created
```

### 12.2 Deployment Process

**Step 1: Prepare Notion Database**
```
1. Create "BBB Revit Standards" database in Notion
2. Set up properties as specified in Section 4.1
3. Populate with initial 10-15 key standards
4. Create Notion integration at https://www.notion.so/my-integrations
5. Share database with integration
6. Copy integration secret (API key)
```

**Step 2: Set Up Extension Directory**
```
1. Create extension directory structure
2. Place all Python files in lib/standards_chat/
3. Place XAML file in lib/ui/
4. Create config directory
5. Add configuration JSON files
6. Add API keys to api_keys.json
7. Create icons
```

**Step 3: Configure PyRevit**
```
1. Copy BBB.extension to PyRevit extensions directory
   - Typically: %APPDATA%\pyRevit\Extensions\
2. Or add to shared network location for team deployment
3. Reload PyRevit
```

**Step 4: Test Installation**
```
1. Open Revit
2. Verify "BBB" tab appears
3. Click "Standards Chat" button
4. Verify window opens
5. Test query: "What are the workset standards?"
6. Verify response with Notion links
```

### 12.3 Team Deployment

**Centralized Deployment**:
```
1. Set up shared network location for PyRevit extensions
   \\bbb-server\IT\Revit\pyRevit\Extensions\BBB.extension\

2. Configure all users' PyRevit to load from network

3. Deploy config files with api_keys.json to:
   \\bbb-server\IT\Revit\Config\standards-chat\

4. Update config_manager.py to read from network location

5. Test with pilot group (5-10 users)

6. Roll out to all users

7. Announce via Slack/email with user guide
```

---

## 13. User Guide

### 13.1 Quick Start

**Opening the Chat**:
1. Look for the "BBB" tab in your Revit ribbon
2. Click the "Standards Chat" button
3. A chat window will open on your screen

**Asking Questions**:
- Type your question in the box at the bottom
- Press Enter or click "Send"
- Wait for the response (usually 5-10 seconds)

**Example Questions**:
- "How should I name worksets?"
- "What view templates should I use for floor plans?"
- "How do I organize levels?"
- "What's the standard for family placement?"
- "How do I fix Guardian warning about [specific warning]?"

**Understanding Responses**:
- Responses include citations to BBB standards
- Blue links take you directly to the full standard in Notion
- Click links to see complete documentation with images

### 13.2 Tips for Better Answers

**Be Specific**:
- ❌ "Tell me about families"
- ✅ "What's the naming convention for door families?"

**Provide Context**:
- ❌ "Is this okay?"
- ✅ "I'm naming a workset 'A-Walls-Ext'. Does this follow our standard?"

**Ask Follow-ups**:
- The chat remembers your conversation
- You can ask "What about interior walls?" after asking about exterior walls

---

## 14. Maintenance & Updates

### 14.1 Updating Standards

**Process**:
1. Edit standards pages in Notion (non-technical staff can do this)
2. No code changes needed - chat automatically uses updated content
3. Consider notifying users of major standard changes

### 14.2 Monitoring & Optimization

**Weekly**:
- Review usage logs for common questions
- Identify gaps in standards documentation
- Check error logs for issues

**Monthly**:
- Analyze which standards are most queried
- Update system prompt if needed
- Review user feedback

**Quarterly**:
- Evaluate if RAG retrieval is effective
- Consider adding new Notion database properties
- Test with new Revit versions

---

## 15. Future Enhancements

### 15.1 Phase 2 Features

1. **Guardian Integration**
   - Query current model warnings
   - Explain Guardian errors with relevant standards
   - "Fix this warning" button that applies standard solution

2. **Multi-modal Support**
   - Screenshot analysis: "Does this follow standards?"
   - Image responses: Show examples from standards

3. **Proactive Suggestions**
   - Detect when user might need help
   - Pop up relevant standards automatically
   - Integration with Revit events

4. **Learning Mode**
   - Quiz users on standards
   - Track knowledge gaps
   - Personalized training suggestions

### 15.2 Phase 3 Features

1. **Standards Authoring Assistant**
   - Help BIM coordinators write new standards
   - Suggest improvements to existing documentation
   - Identify contradictions across standards

2. **Project-Specific Context**
   - Remember project-specific decisions
   - Track deviations from standards
   - Generate project closeout documentation

3. **Advanced Analytics**
   - Dashboard for DCT team
   - Standards coverage heatmap
   - User proficiency tracking

---

## 16. Success Metrics

### 16.1 Key Performance Indicators

**Usage Metrics**:
- Daily active users
- Queries per user per week
- Average response satisfaction (thumbs up/down)

**Efficiency Metrics**:
- Time saved vs. manual standards lookup
- Reduction in repeated questions to BIM coordinators
- Guardian warnings resolved via chat

**Quality Metrics**:
- Accuracy of responses (spot checks)
- Relevance of retrieved standards
- User feedback scores

**Target Metrics (6 months)**:
- 70% of Revit users active monthly
- 4.0+ average satisfaction rating (1-5 scale)
- 50% reduction in standards-related Slack questions

---

## 17. Support & Troubleshooting

### 17.1 Common Issues

**Chat won't open**:
```
Cause: Missing dependencies or API keys
Fix: 
1. Check config files exist
2. Verify API keys are valid
3. Check pyRevit console for errors (Ctrl+F8)
```

**No response to queries**:
```
Cause: API rate limit or network issue
Fix:
1. Wait 1 minute and try again
2. Check internet connection
3. Verify API keys haven't expired
```

**Responses not relevant**:
```
Cause: Notion standards need better keywords
Fix:
1. Add more searchable keywords to Notion pages
2. Improve page titles and headings
3. Add "Keywords" property in Notion
```

### 17.2 Getting Help

**For Users**:
1. Check user guide in Notion
2. Ask your studio BIM coordinator
3. Post in #bim-support Slack channel

**For Developers/IT**:
1. Check error logs: `BBB.extension/logs/errors.log`
2. Check usage logs: `BBB.extension/logs/usage.jsonl`
3. Contact DCT team: [email addresses]

---

## 18. Conclusion

This specification provides a complete blueprint for building a Revit Standards Assistant using PyRevit, Notion as a RAG database, and Claude for natural language understanding.

**Key Advantages of This Approach**:
- **Easy content management**: Non-technical staff can update standards
- **Fast development**: PyRevit allows rapid iteration
- **Flexible deployment**: Can be updated without reinstalling
- **Scalable**: Can grow with additional features and data sources
- **User-friendly**: Familiar chat interface, no training needed

**Next Steps**:
1. Set up Notion database and populate initial standards
2. Obtain API keys
3. Implement core components (Notion client, Anthropic client)
4. Build UI
5. Test with small pilot group
6. Iterate based on feedback
7. Deploy to full team

The system can be built incrementally, starting with basic query/response and adding advanced features (Guardian integration, context awareness) later.

---

**Document Version**: 1.0  
**Last Updated**: November 2025  
**Author**: Technical Specification for BBB DCT Team


# Enhanced Specification: Context-Aware Features

## Additional Section 6.8: Context Awareness Module

Let me add comprehensive context awareness capabilities to the specification:

---

## 6.8 Context Awareness Module (context_awareness.py)

```python
"""
Context Awareness Module
Extracts detailed Revit context including selected elements and screenshots
"""

import clr
clr.AddReference('System.Drawing')
clr.AddReference('System.Windows.Forms')

from System.Drawing import Bitmap, Imaging
from System.Drawing.Imaging import ImageFormat
from System.IO import MemoryStream, File
from System import Convert, Array, Byte
import os
import base64

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *
from pyrevit import revit, DB, UI


class RevitContextExtractor:
    """Extract rich context from current Revit session"""
    
    def __init__(self):
        self.doc = revit.doc
        self.uidoc = revit.uidoc
        self.app = revit.doc.Application
    
    def get_full_context(self, include_screenshot=False, include_selection=True):
        """
        Get comprehensive Revit context
        
        Args:
            include_screenshot (bool): Capture and encode current view
            include_selection (bool): Get detailed selection info
            
        Returns:
            dict: Context dictionary with all available information
        """
        context = {
            'document': self._get_document_context(),
            'view': self._get_view_context(),
            'workset': self._get_workset_context(),
            'phase': self._get_phase_context(),
        }
        
        if include_selection:
            selection_context = self._get_selection_context()
            if selection_context:
                context['selection'] = selection_context
        
        if include_screenshot:
            screenshot = self._capture_view_screenshot()
            if screenshot:
                context['screenshot'] = screenshot
        
        return context
    
    def _get_document_context(self):
        """Get document-level information"""
        if not self.doc:
            return None
        
        return {
            'project_name': self.doc.Title or 'Untitled',
            'project_number': self.doc.ProjectInformation.Number if hasattr(self.doc.ProjectInformation, 'Number') else None,
            'is_workshared': self.doc.IsWorkshared,
            'is_family': self.doc.IsFamilyDocument,
            'revit_version': self.app.VersionNumber,
            'revit_build': self.app.VersionBuild,
            'central_model_path': self.doc.GetWorksharingCentralModelPath().CentralServerPath if self.doc.IsWorkshared else None
        }
    
    def _get_view_context(self):
        """Get active view information"""
        active_view = self.doc.ActiveView
        if not active_view:
            return None
        
        context = {
            'view_name': active_view.Name,
            'view_type': active_view.ViewType.ToString(),
            'view_id': active_view.Id.IntegerValue,
            'scale': active_view.Scale if hasattr(active_view, 'Scale') else None,
            'detail_level': active_view.DetailLevel.ToString() if hasattr(active_view, 'DetailLevel') else None,
            'discipline': active_view.Discipline.ToString() if hasattr(active_view, 'Discipline') else None,
        }
        
        # View template
        template_id = active_view.ViewTemplateId
        if template_id and template_id != ElementId.InvalidElementId:
            template = self.doc.GetElement(template_id)
            if template:
                context['view_template'] = template.Name
        
        # Associated level for plan views
        if hasattr(active_view, 'GenLevel') and active_view.GenLevel:
            context['level'] = active_view.GenLevel.Name
        
        # Phase
        if hasattr(active_view, 'Phase') and active_view.Phase:
            context['phase'] = active_view.Phase.Name
        
        return context
    
    def _get_workset_context(self):
        """Get workset information"""
        if not self.doc.IsWorkshared:
            return None
        
        try:
            workset_table = self.doc.GetWorksetTable()
            active_workset_id = workset_table.GetActiveWorksetId()
            active_workset = workset_table.GetWorkset(active_workset_id)
            
            # Get all worksets
            all_worksets = []
            for workset_id in workset_table.GetWorksetIds():
                workset = workset_table.GetWorkset(workset_id)
                if workset.Kind == WorksetKind.UserWorkset:
                    all_worksets.append({
                        'name': workset.Name,
                        'id': workset_id.IntegerValue,
                        'is_active': workset_id == active_workset_id,
                        'is_open': workset.IsOpen,
                        'is_editable': workset.IsEditable
                    })
            
            return {
                'active_workset': active_workset.Name,
                'active_workset_id': active_workset_id.IntegerValue,
                'all_worksets': all_worksets,
                'workset_count': len(all_worksets)
            }
        except:
            return None
    
    def _get_phase_context(self):
        """Get phase information"""
        try:
            phases = []
            phase_collector = FilteredElementCollector(self.doc).OfClass(Phase)
            
            for phase in phase_collector:
                phases.append({
                    'name': phase.Name,
                    'id': phase.Id.IntegerValue
                })
            
            return {
                'phases': phases,
                'phase_count': len(phases)
            }
        except:
            return None
    
    def _get_selection_context(self):
        """Get detailed information about selected elements"""
        if not self.uidoc:
            return None
        
        selection = self.uidoc.Selection
        selected_ids = list(selection.GetElementIds())
        
        if not selected_ids:
            return None
        
        selected_elements = []
        
        for elem_id in selected_ids[:10]:  # Limit to first 10 elements
            element = self.doc.GetElement(elem_id)
            if not element:
                continue
            
            elem_info = self._extract_element_info(element)
            if elem_info:
                selected_elements.append(elem_info)
        
        return {
            'selection_count': len(selected_ids),
            'elements': selected_elements,
            'truncated': len(selected_ids) > 10
        }
    
    def _extract_element_info(self, element):
        """Extract detailed information from a single element"""
        try:
            info = {
                'id': element.Id.IntegerValue,
                'category': element.Category.Name if element.Category else 'No Category',
                'name': element.Name if hasattr(element, 'Name') else None,
            }
            
            # Element type
            type_id = element.GetTypeId()
            if type_id and type_id != ElementId.InvalidElementId:
                elem_type = self.doc.GetElement(type_id)
                if elem_type:
                    info['type_name'] = elem_type.Name
                    info['family_name'] = elem_type.FamilyName if hasattr(elem_type, 'FamilyName') else None
            
            # Workset
            if self.doc.IsWorkshared:
                workset_id = element.WorksetId
                if workset_id and workset_id != WorksetId.InvalidWorksetId:
                    workset = self.doc.GetWorksetTable().GetWorkset(workset_id)
                    info['workset'] = workset.Name
            
            # Level
            level_param = element.get_Parameter(BuiltInParameter.FAMILY_LEVEL_PARAM)
            if not level_param:
                level_param = element.get_Parameter(BuiltInParameter.SCHEDULE_LEVEL_PARAM)
            
            if level_param and level_param.HasValue:
                level_id = level_param.AsElementId()
                if level_id != ElementId.InvalidElementId:
                    level = self.doc.GetElement(level_id)
                    if level:
                        info['level'] = level.Name
            
            # Phase Created
            phase_created = element.get_Parameter(BuiltInParameter.PHASE_CREATED)
            if phase_created and phase_created.HasValue:
                phase_id = phase_created.AsElementId()
                phase = self.doc.GetElement(phase_id)
                if phase:
                    info['phase_created'] = phase.Name
            
            # Key parameters based on category
            info['parameters'] = self._extract_key_parameters(element)
            
            # Design option
            design_option = element.DesignOption
            if design_option:
                info['design_option'] = design_option.Name
            
            return info
            
        except Exception as e:
            print("Error extracting element info: {}".format(str(e)))
            return None
    
    def _extract_key_parameters(self, element):
        """Extract key parameters based on element category"""
        params = {}
        
        # Common parameters to check
        key_params = [
            'Mark',
            'Comments',
            'Type Comments',
            'Length',
            'Width',
            'Height',
            'Area',
            'Volume',
            'Thickness',
            'Offset',
            'Function'  # For walls
        ]
        
        for param_name in key_params:
            param = element.LookupParameter(param_name)
            if param and param.HasValue:
                param_value = self._get_parameter_value(param)
                if param_value:
                    params[param_name] = param_value
        
        return params
    
    def _get_parameter_value(self, parameter):
        """Get parameter value as string"""
        try:
            storage_type = parameter.StorageType
            
            if storage_type == StorageType.String:
                return parameter.AsString()
            elif storage_type == StorageType.Integer:
                return str(parameter.AsInteger())
            elif storage_type == StorageType.Double:
                # Check if it's a length/area/volume that needs unit conversion
                if parameter.Definition.ParameterType == ParameterType.Length:
                    return "{:.2f}".format(parameter.AsDouble())
                return "{:.3f}".format(parameter.AsDouble())
            elif storage_type == StorageType.ElementId:
                elem_id = parameter.AsElementId()
                if elem_id and elem_id != ElementId.InvalidElementId:
                    elem = self.doc.GetElement(elem_id)
                    if elem:
                        return elem.Name
            
            return parameter.AsValueString()
        except:
            return None
    
    def _capture_view_screenshot(self):
        """
        Capture screenshot of active view and encode as base64
        
        Returns:
            dict: Screenshot data with base64 encoding and metadata
        """
        try:
            active_view = self.doc.ActiveView
            
            # Create image export options
            export_options = ImageExportOptions()
            export_options.ZoomType = ZoomFitType.FitToPage
            export_options.PixelSize = 1920  # Width in pixels
            export_options.ImageResolution = ImageResolution.DPI_150
            export_options.FitDirection = FitDirectionType.Horizontal
            export_options.ExportRange = ExportRange.SetOfViews
            export_options.SetViewsAndSheets([active_view.Id])
            
            # Export to temporary file
            temp_dir = os.path.join(os.environ['TEMP'], 'RevitChat')
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            
            temp_path = os.path.join(temp_dir, "view_capture")
            export_options.FilePath = temp_path
            
            # Export
            self.doc.ExportImage(export_options)
            
            # Read the exported image (Revit adds .png extension)
            image_path = temp_path + ".png"
            
            if os.path.exists(image_path):
                # Read and encode as base64
                with open(image_path, 'rb') as image_file:
                    image_data = image_file.read()
                    base64_data = base64.b64encode(image_data).decode('utf-8')
                
                # Clean up temp file
                try:
                    os.remove(image_path)
                except:
                    pass
                
                return {
                    'base64': base64_data,
                    'format': 'png',
                    'view_name': active_view.Name,
                    'size_kb': len(image_data) // 1024
                }
            
            return None
            
        except Exception as e:
            print("Error capturing screenshot: {}".format(str(e)))
            return None
    
    def format_context_for_prompt(self, context, include_screenshot=False):
        """
        Format context dictionary into readable text for Claude prompt
        
        Args:
            context (dict): Context dictionary from get_full_context()
            include_screenshot (bool): Whether screenshot is included
            
        Returns:
            str: Formatted context string
        """
        lines = ["# Current Revit Context\n"]
        
        # Document info
        if context.get('document'):
            lines.append("## Project Information")
            doc = context['document']
            lines.append("- Project: {}".format(doc.get('project_name', 'Unknown')))
            if doc.get('project_number'):
                lines.append("- Project Number: {}".format(doc['project_number']))
            lines.append("- Revit Version: {}".format(doc.get('revit_version', 'Unknown')))
            lines.append("- Workshared: {}".format('Yes' if doc.get('is_workshared') else 'No'))
            lines.append("")
        
        # View info
        if context.get('view'):
            lines.append("## Active View")
            view = context['view']
            lines.append("- View Name: {}".format(view.get('view_name', 'Unknown')))
            lines.append("- View Type: {}".format(view.get('view_type', 'Unknown')))
            if view.get('view_template'):
                lines.append("- View Template: {}".format(view['view_template']))
            if view.get('level'):
                lines.append("- Level: {}".format(view['level']))
            if view.get('scale'):
                lines.append("- Scale: 1:{}".format(view['scale']))
            if view.get('detail_level'):
                lines.append("- Detail Level: {}".format(view['detail_level']))
            lines.append("")
        
        # Workset info
        if context.get('workset'):
            lines.append("## Worksets")
            ws = context['workset']
            lines.append("- Active Workset: {}".format(ws.get('active_workset', 'Unknown')))
            lines.append("- Total Worksets: {}".format(ws.get('workset_count', 0)))
            lines.append("")
        
        # Selection info
        if context.get('selection'):
            lines.append("## Current Selection")
            sel = context['selection']
            lines.append("- Selected Elements: {}".format(sel.get('selection_count', 0)))
            
            if sel.get('elements'):
                lines.append("\n### Selected Element Details:")
                for i, elem in enumerate(sel['elements'], 1):
                    lines.append("\n#### Element {}:".format(i))
                    lines.append("- Category: {}".format(elem.get('category', 'Unknown')))
                    
                    if elem.get('family_name') and elem.get('type_name'):
                        lines.append("- Family: {}".format(elem['family_name']))
                        lines.append("- Type: {}".format(elem['type_name']))
                    elif elem.get('name'):
                        lines.append("- Name: {}".format(elem['name']))
                    
                    if elem.get('workset'):
                        lines.append("- Workset: {}".format(elem['workset']))
                    if elem.get('level'):
                        lines.append("- Level: {}".format(elem['level']))
                    if elem.get('phase_created'):
                        lines.append("- Phase: {}".format(elem['phase_created']))
                    
                    if elem.get('parameters'):
                        lines.append("- Key Parameters:")
                        for param_name, param_value in elem['parameters'].items():
                            lines.append("  - {}: {}".format(param_name, param_value))
            
            if sel.get('truncated'):
                lines.append("\n(Showing first 10 of {} selected elements)".format(sel['selection_count']))
            lines.append("")
        
        # Screenshot note
        if include_screenshot and context.get('screenshot'):
            lines.append("## Visual Context")
            lines.append("A screenshot of the current view has been included for visual analysis.")
            lines.append("")
        
        return "\n".join(lines)


# Helper function for easy import
def extract_revit_context(include_screenshot=False, include_selection=True):
    """
    Helper function to extract Revit context
    
    Args:
        include_screenshot (bool): Capture screenshot of active view
        include_selection (bool): Include selected element details
        
    Returns:
        dict: Context dictionary
    """
    extractor = RevitContextExtractor()
    return extractor.get_full_context(
        include_screenshot=include_screenshot,
        include_selection=include_selection
    )
```

---

## Updated Section 6.3: Enhanced Chat Window with Context Controls

Add these UI elements to the XAML:

```xml
<!-- Add to the input area, above the existing input box -->
<StackPanel Orientation="Horizontal" Margin="0,0,0,10">
    <CheckBox x:Name="IncludeScreenshotCheckbox"
              Content="📸 Include Screenshot"
              VerticalAlignment="Center"
              Margin="0,0,15,0"
              ToolTip="Attach a screenshot of the current view for visual analysis"/>
    
    <CheckBox x:Name="IncludeSelectionCheckbox"
              Content="🎯 Analyze Selection"
              VerticalAlignment="Center"
              IsChecked="True"
              ToolTip="Include details about currently selected elements"/>
    
    <Button x:Name="QuickContextButton"
           Content="🔍 Quick Context"
           Height="24"
           Padding="8,0"
           Margin="15,0,0,0"
           Background="#F0F0F0"
           BorderBrush="#D0D0D0"
           BorderThickness="1"
           Cursor="Hand"
           ToolTip="Show current Revit context without asking a question"/>
</StackPanel>
```

Update the `send_message` method in chat_window.py:

```python
def send_message(self):
    """Send user message and get response with context"""
    user_input = self.input_textbox.Text.strip()
    
    if not user_input:
        return
    
    # Clear input
    self.input_textbox.Clear()
    
    # Check context options
    include_screenshot = self.include_screenshot_checkbox.IsChecked
    include_selection = self.include_selection_checkbox.IsChecked
    
    # Add user message to UI
    self.add_message(user_input, is_user=True)
    
    # Show appropriate loading message
    if include_screenshot:
        self.show_loading("Capturing screenshot...")
    elif include_selection:
        self.show_loading("Analyzing selection...")
    else:
        self.show_loading("Searching standards...")
    
    # Process in background thread
    def process_query():
        try:
            # Extract Revit context
            self.update_loading_status("Extracting Revit context...")
            
            context_extractor = RevitContextExtractor()
            revit_context = context_extractor.get_full_context(
                include_screenshot=include_screenshot,
                include_selection=include_selection
            )
            
            # Format context for prompt
            formatted_context = context_extractor.format_context_for_prompt(
                revit_context,
                include_screenshot=include_screenshot
            )
            
            # Search Notion
            self.update_loading_status("Searching standards...")
            relevant_pages = self.notion.search_standards(user_input)
            
            # Get response from Claude
            self.update_loading_status("Generating response...")
            response = self.anthropic.get_response(
                user_query=user_input,
                notion_pages=relevant_pages,
                revit_context=formatted_context,
                screenshot=revit_context.get('screenshot'),
                conversation_history=self.conversation
            )
            
            # Update conversation and display
            self.conversation.append({
                'user': user_input,
                'assistant': response['text'],
                'sources': response['sources']
            })
            
            self.Dispatcher.Invoke(
                lambda: self.add_message(
                    response['text'],
                    is_user=False,
                    sources=response['sources']
                )
            )
            
        except Exception as e:
            error_msg = "Sorry, I encountered an error: {}".format(str(e))
            self.Dispatcher.Invoke(
                lambda: self.add_message(error_msg, is_user=False)
            )
        
        finally:
            self.Dispatcher.Invoke(self.hide_loading)
    
    # Start background thread
    thread = Thread(ThreadStart(process_query))
    thread.IsBackground = True
    thread.Start()
```

---

## Updated Section 6.5: Enhanced Anthropic Client with Vision

Update the Anthropic client to support image analysis:

```python
def get_response(self, user_query, notion_pages, revit_context=None, 
                 screenshot=None, conversation_history=None):
    """
    Get response from Claude with RAG context and optional image
    
    Args:
        user_query (str): User's question
        notion_pages (list): Relevant Notion pages
        revit_context (str): Formatted Revit context string
        screenshot (dict): Optional screenshot with base64 data
        conversation_history (list): Previous conversation
        
    Returns:
        dict: Response with text and sources
    """
    # Build context from Notion pages
    notion_context = self._build_notion_context(notion_pages)
    
    # Build messages array
    messages = self._build_messages(
        user_query, 
        notion_context,
        revit_context,
        screenshot,
        conversation_history
    )
    
    # Make API call
    response_data = self._call_api(messages)
    
    # Extract response
    response_text = response_data['content'][0]['text']
    
    # Format sources
    sources = [
        {
            'title': page['title'],
            'url': page['url'],
            'category': page.get('category', 'General')
        }
        for page in notion_pages
    ]
    
    return {
        'text': response_text,
        'sources': sources
    }

def _build_messages(self, user_query, notion_context, revit_context, 
                    screenshot, conversation_history):
    """Build messages array for API call with optional image"""
    messages = []
    
    # Add conversation history (last 3 exchanges)
    if conversation_history:
        recent_history = conversation_history[-3:]
        for exchange in recent_history:
            messages.append({
                "role": "user",
                "content": exchange['user']
            })
            messages.append({
                "role": "assistant",
                "content": exchange['assistant']
            })
    
    # Build current user message
    content_blocks = []
    
    # Add screenshot if present (image must come first for Claude)
    if screenshot and screenshot.get('base64'):
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": screenshot['base64']
            }
        })
    
    # Build text content
    text_parts = []
    
    if notion_context:
        text_parts.append(notion_context)
    
    if revit_context:
        text_parts.append(revit_context)
    
    text_parts.append("User Question: {}".format(user_query))
    
    # Add instructions
    if screenshot:
        text_parts.append("""
Please provide a helpful answer based on:
1. The screenshot of the current Revit view (analyze what you see)
2. BBB's standards documentation above
3. The current Revit context provided

When analyzing the screenshot:
- Identify any standards violations or concerns
- Suggest improvements based on BBB standards
- Reference specific elements you can see
- Be specific about visual issues

When referencing standards, mention them by name and explain how they apply to what's shown.""")
    else:
        text_parts.append("""
Please provide a helpful, detailed answer based on:
1. BBB's standards documentation above
2. The current Revit context (selected elements, active view, etc.)

When referencing specific standards, mention them by name.
If the user is asking about selected elements, provide specific guidance for those elements.
If multiple standards are relevant, explain how they work together.""")
    
    content_blocks.append({
        "type": "text",
        "text": "\n\n".join(text_parts)
    })
    
    messages.append({
        "role": "user",
        "content": content_blocks
    })
    
    return messages
```

---

## New Section 13.3: Context-Aware Usage Examples

### Using Selection Analysis

**Scenario 1: Check if a wall follows standards**
1. Select a wall in Revit
2. Open Standards Chat
3. Make sure "🎯 Analyze Selection" is checked
4. Ask: "Does this wall follow our standards?"
5. Claude will analyze:
   - Wall type and family
   - Workset assignment
   - Level placement
   - Any non-standard parameters
   - Suggest corrections if needed

**Scenario 2: Get guidance for multiple elements**
1. Select several doors
2. Ask: "Are these doors placed correctly?"
3. Claude will check:
   - Family naming conventions
   - Workset assignments
   - Consistency across selection
   - Standard versus non-standard types

### Using Screenshot Analysis

**Scenario 1: Review view setup**
1. Open Standards Chat
2. Check "📸 Include Screenshot"
3. Ask: "Is my view set up correctly for a design development section?"
4. Claude will analyze:
   - View template compliance
   - Detail level appropriateness
   - Annotation visibility
   - Visual standards compliance

**Scenario 2: Check modeling quality**
1. Navigate to problem area in model
2. Include screenshot
3. Ask: "What modeling issues do you see here?"
4. Claude will identify:
   - Visible gaps or overlaps
   - Elements that don't align
   - Non-standard representations
   - Suggestions for fixes

### Example Queries with Context

**Without Context**:
- "How should walls be modeled?"
- "What's the workset standard?"

**With Selection Context**:
- "Is this wall on the right workset?" *(with wall selected)*
- "Should I change the type of these doors?" *(with doors selected)*
- "Why is Guardian flagging this element?" *(with flagged element selected)*

**With Screenshot Context**:
- "Does this section view follow our standards?" *(with screenshot)*
- "What's wrong with this plan view?" *(with screenshot)*
- "How can I make this look more like our standard sections?" *(with screenshot)*

**With Both**:
- "I selected this wall - why does it look wrong in the view?" *(screenshot + selection)*
- "Are these families placed correctly according to our standards?" *(screenshot + selection)*

---

## Updated Section 7.1: Enhanced System Prompt

```
You are a helpful Revit standards assistant for Beyer Blinder Belle (BBB), an architecture firm with 150+ Revit users across 5 studios.

Your role is to help users understand and apply BBB's Revit standards by:
1. Answering questions clearly and accurately based on provided standards
2. Analyzing Revit context (selected elements, active views, worksets, etc.)
3. Reviewing screenshots to identify standards compliance issues
4. Providing specific, actionable guidance
5. Citing sources by referencing standard names
6. Explaining the reasoning behind standards
7. Being concise but thorough

When Revit context is provided:
- Pay close attention to selected element details (category, type, workset, level, parameters)
- Consider the active view type and settings
- Reference specific element properties in your answers
- Identify any standards violations in the selection
- Provide targeted fixes for the specific elements selected

When a screenshot is provided:
- Carefully analyze what you see in the Revit view
- Identify specific elements, their arrangement, and visual quality
- Compare what you see to BBB standards
- Point out specific issues by location ("the wall on the left", "the door in the center")
- Suggest visual improvements based on standards
- Be specific about what needs to change and why

Communication style:
- Professional but friendly
- Use technical Revit terminology accurately
- Be specific when analyzing elements ("This Wall Type 'EXT-Brick-8IN' on Workset 'A-WALL-EXT'...")
- Provide step-by-step fixes when appropriate
- Don't over-explain to experienced users

Element Analysis Priority:
1. Standards compliance (naming, workset, parameters)
2. Consistency with BBB practices
3. Technical correctness
4. Efficiency and best practices

Visual Analysis Priority:
1. Standards violations visible in the view
2. Modeling quality issues (gaps, overlaps, alignment)
3. View setup compliance (templates, filters, detail level)
4. Documentation quality

Remember: You're analyzing ACTUAL elements and views from the user's live Revit model. Be specific and actionable.
```

---

## New Section 14.3: Context-Aware Features Troubleshooting

### Screenshot Issues

**Screenshot fails to capture**:
```
Possible causes:
- View is 3D and too complex to export
- Insufficient disk space in TEMP folder
- Export permissions issue

Solutions:
1. Try a 2D view instead
2. Clear temp files: %TEMP%\RevitChat\
3. Check disk space
4. Try without screenshot first
```

**Screenshot shows unexpected view**:
```
Cause: Wrong view is active
Fix: Make sure correct view is active before taking screenshot
```

### Selection Analysis Issues

**"No selection detected"**:
```
Cause: Nothing selected in Revit
Fix: Select elements before asking question
```

**Element details seem wrong**:
```
Cause: Element properties may have changed since selection
Fix: Ask question immediately after selecting elements
```

**Too much information returned**:
```
Cause: Many elements selected (>10)
Behavior: System shows first 10 with note about truncation
Solution: Select fewer elements for detailed analysis
```

---

## Updated Section 11.3: Context-Aware Testing

Add these test scenarios:

```python
def test_selection_context_extraction():
    """Test extracting info from selected elements"""
    # Select a wall in test model
    # (Requires test Revit document)
    
    extractor = RevitContextExtractor()
    context = extractor.get_full_context(
        include_screenshot=False,
        include_selection=True
    )
    
    assert context['selection'] is not None
    assert context['selection']['selection_count'] > 0
    assert len(context['selection']['elements']) > 0
    
    # Check element has key properties
    element = context['selection']['elements'][0]
    assert 'category' in element
    assert 'workset' in element or not revit.doc.IsWorkshared

def test_screenshot_capture():
    """Test capturing and encoding screenshot"""
    extractor = RevitContextExtractor()
    context = extractor.get_full_context(
        include_screenshot=True,
        include_selection=False
    )
    
    assert context['screenshot'] is not None
    assert 'base64' in context['screenshot']
    assert len(context['screenshot']['base64']) > 0
    assert context['screenshot']['format'] == 'png'

def test_context_formatting():
    """Test formatting context for prompt"""
    extractor = RevitContextExtractor()
    context = extractor.get_full_context(
        include_screenshot=False,
        include_selection=True
    )
    
    formatted = extractor.format_context_for_prompt(context, False)
    
    assert len(formatted) > 0
    assert 'Project Information' in formatted
    assert 'Active View' in formatted
```

---

## Performance Considerations

### Screenshot Size Management

Screenshots can be large. Implement size limits:

```python
def _optimize_screenshot(self, screenshot_data):
    """Optimize screenshot size for API"""
    max_size_kb = 5000  # 5MB limit for Anthropic API
    
    if screenshot_data['size_kb'] > max_size_kb:
        # Reduce resolution
        # Re-export with lower DPI
        export_options.ImageResolution = ImageResolution.DPI_72
        # Re-capture...
    
    return screenshot_data
```

### Caching Context

Cache non-changing context to improve performance:

```python
class ContextCache:
    """Cache document-level context that doesn't change frequently"""
    
    def __init__(self, ttl_seconds=300):
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get_document_context(self, doc):
        """Get cached document context or extract fresh"""
        doc_id = doc.Title
        
        if doc_id in self.cache:
            cached_time, cached_data = self.cache[doc_id]
            if time.time() - cached_time < self.ttl:
                return cached_data
        
        # Extract fresh context
        extractor = RevitContextExtractor()
        context = extractor._get_document_context()
        
        self.cache[doc_id] = (time.time(), context)
        return context
```
