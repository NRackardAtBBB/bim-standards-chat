# BBB Standards Assistant - PyRevit Extension

AI-powered Revit standards assistant using Notion RAG and Claude AI.

## Overview

The BBB Standards Assistant is a PyRevit extension that provides an in-Revit chat interface to query BBB's Revit standards documentation stored in Notion. It uses Retrieval-Augmented Generation (RAG) with Claude AI to provide accurate, contextual answers with source citations.

## Features

- 🤖 **AI-Powered Chat**: Natural language queries about Revit standards
- 📚 **Notion Integration**: Searches and retrieves documentation from Notion database
- 🔗 **Source Citations**: Provides clickable links to full documentation
- 🎯 **Context-Aware**: Considers current Revit context (view, workset, selection)
- 💬 **Conversation History**: Maintains context across multiple questions
- ⚡ **Fast & Efficient**: Parallel API calls and smart caching

## Architecture

```
Revit User
    ↓
PyRevit Chat Interface (WPF)
    ↓
Query Processing
    ↓
┌─────────────┬──────────────┐
│ Notion RAG  │ Claude API   │
│ (Search)    │ (Generation) │
└─────────────┴──────────────┘
    ↓
Response with Citations
```

## Installation

### Prerequisites

- Autodesk Revit 2023, 2024, or 2025
- PyRevit 4.8.x or higher installed
- Notion API access
- Anthropic API access (Claude)

### Steps

1. **Clone or download this repository**:
   ```
   git clone <repository-url>
   ```

2. **Copy the extension to PyRevit extensions folder**:
   ```
   %APPDATA%\pyRevit\Extensions\
   ```
   
   Your folder structure should look like:
   ```
   %APPDATA%\pyRevit\Extensions\BBB.extension\
   ```

3. **Configure API Keys**:
   - Navigate to `BBB.extension\config\`
   - Edit `api_keys.json` with your credentials:
     ```json
     {
       "notion_api_key": "secret_your_actual_key_here",
       "anthropic_api_key": "sk-ant-your_actual_key_here"
     }
     ```

4. **Configure Notion Database**:
   - Edit `config.json` and set your Notion database ID:
     ```json
     {
       "notion": {
         "database_id": "your-actual-database-id-here",
         ...
       }
     }
     ```

5. **Reload PyRevit**:
   - In Revit, go to PyRevit tab → Reload
   - You should see a new "BBB" tab with "Standards Assistant" panel

## Configuration

### Obtaining API Keys

#### Notion API Key

1. Go to https://www.notion.so/my-integrations
2. Click "New Integration"
3. Name it "BBB Standards Assistant"
4. Select the workspace
5. Copy the "Internal Integration Token" (starts with `secret_`)
6. Share your standards database with this integration

#### Anthropic API Key

1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to API Keys
4. Create a new key
5. Copy the key (starts with `sk-ant-`)

### Notion Database Setup

Your Notion database should have these properties:

| Property | Type | Description |
|----------|------|-------------|
| Title | Title | Standard name |
| Category | Select | Category (Modeling, Views, Worksets, etc.) |
| Studio | Multi-select | Applicable studios |
| Revit Version | Multi-select | Compatible versions |
| Status | Select | Active, Draft, Deprecated |
| Last Updated | Date | Last modification date |
| Owner | Person | Document owner |
| Keywords | Multi-select | Searchable tags |
| Priority | Select | Critical, Important, Reference |

### Configuration Options

Edit `config.json` to customize:

- `notion.max_search_results`: Number of pages to retrieve (default: 5)
- `anthropic.model`: Claude model to use (default: claude-sonnet-4-20250514)
- `anthropic.max_tokens`: Maximum response length (default: 2048)
- `anthropic.temperature`: Response creativity (default: 0.7)
- `ui.window_width/height`: Chat window dimensions

## Usage

### Opening the Chat

1. In Revit, click the **BBB** tab
2. In the **Standards Assistant** panel, click **Standards Chat**
3. The chat window will open

### Asking Questions

Simply type your question in natural language:

**Examples:**
- "What's the workset naming convention?"
- "How should I organize levels?"
- "What view template should I use for floor plans?"
- "How do I fix Guardian error about duplicate levels?"

### Executable Actions

The assistant can suggest **executable actions** that appear as blue buttons in the chat. Click these buttons to perform actions directly in Revit without manual work.

#### Available Actions:

**1. Select Elements**
- Select elements by category, parameter values, or workset
- Example: "Select all doors without mark values"
- Example: "Find all walls on the wrong workset"

**2. Update Parameters**
- Batch update parameter values on selected elements
- Example: "Update the comments parameter to 'Verified' for my selection"

**3. Change Workset**
- Move selected elements to a different workset
- Example: "Move these elements to the A-FURN workset"

**4. Apply View Template**
- Apply a view template to the active view
- Example: "Apply the standard floor plan view template"

**5. Isolate Elements**
- Temporarily isolate selected elements in the current view
- Example: "Isolate these elements so I can see them better"

**6. Check Standards**
- Validate selected elements against BBB standards
- Example: "Check if my selection follows BBB standards"

#### How Action Buttons Work:

1. Ask the assistant to perform an action
2. A **blue button** appears in the chat with the action description
3. Click the button to execute immediately (no confirmation needed)
4. The button updates to show "✓ Completed" or "✗ Failed"
5. A success message confirms what was done

**Tips:**
- The chat window stays on top while actions execute
- Actions happen instantly when you click the button
- You can ask follow-up questions after an action completes
- Multiple actions can be chained together conversationally


**Tips:**
- Be specific about what you're working on
- The assistant will consider your current Revit context
- Ask follow-up questions to get more details
- Click source links to read full documentation

### Keyboard Shortcuts

- **Ctrl+Enter**: Send message
- **Enter**: New line in message

### Settings

Click the **Settings** button to:
- Open the config folder
- View current configuration
- Access API key files

## File Structure

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
│   │   ├── chat_window.py          # WPF window controller
│   │   ├── notion_client.py        # Notion API wrapper
│   │   ├── anthropic_client.py     # Claude API wrapper
│   │   ├── config_manager.py       # Configuration handler
│   │   └── utils.py                # Utility functions
│   └── ui/
│       └── chat_window.xaml        # WPF UI definition
└── config/
    ├── config.json                 # Application settings
    ├── api_keys.json              # API credentials (git-ignored)
    └── .gitignore
```

## Development

### Technologies

- **PyRevit**: IronPython 2.7.x framework
- **WPF/XAML**: User interface
- **Notion API**: Document storage and retrieval
- **Anthropic Claude**: AI language model
- **.NET HTTP Client**: API communication

### Extending

To add new features:

1. **Custom Context Extraction**: Modify `utils.py::extract_revit_context()`
2. **UI Customization**: Edit `chat_window.xaml`
3. **Response Processing**: Extend `anthropic_client.py`
4. **Search Logic**: Modify `notion_client.py`

### Testing

Test in Revit:
1. Make changes to code
2. Reload PyRevit (PyRevit tab → Reload)
3. Test functionality in a sample project

### Debugging

Enable debug logging in `config.json`:
```json
{
  "logging": {
    "enabled": true,
    "log_file": "standards_chat.log"
  }
}
```

Logs will be written to the extension directory.

## Troubleshooting

### "Configuration file not found"
- Ensure the extension is in the correct folder
- Check that `config/config.json` and `config/api_keys.json` exist

### "API key not configured"
- Open Settings button to locate config folder
- Edit `api_keys.json` with valid keys
- Keys should NOT contain placeholder text like "your-" or "xxxxx"

### "No standards found"
- Check your Notion database ID is correct
- Ensure the integration has access to the database
- Verify database pages have Status = "Active"

### "Connection error"
- Check internet connectivity
- Verify API keys are valid
- Check if Notion/Anthropic services are accessible

### Window doesn't open
- Check PyRevit output window for errors
- Verify all dependencies are in place
- Try reloading PyRevit

## Security

- **API Keys**: Never commit `api_keys.json` to version control
- **Access Control**: Use workspace-level Notion integrations
- **Rate Limiting**: Built-in throttling prevents API quota issues
- **Data Privacy**: Queries are sent to Anthropic (review their data policy)

## Support

For issues, questions, or feature requests:
- Contact the BBB DCT Team
- Review the Development document for technical details
- Check PyRevit logs for error messages

## License

Internal tool for Beyer Blinder Belle. Not for external distribution.

## Credits

Developed by BBB DCT Team
- PyRevit by Ehsan Iran-Nejad
- Notion API by Notion Labs
- Claude AI by Anthropic

---

**Version**: 1.0.0  
**Last Updated**: 2025-01-14  
**Revit Compatibility**: 2023, 2024, 2025  
**PyRevit Version**: 4.8.x or higher
