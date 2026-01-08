# Kodama - Setup Guide

This guide will walk you through setting up Kodama from scratch.

## Part 1: Prerequisites

### Required Accounts & Access

1. **Notion Account**
   - Your team's Notion workspace
   - Admin or ability to create integrations
   - Access to create/manage databases

2. **Anthropic Account**
   - Sign up at https://console.anthropic.com/
   - Credit card for API usage (pay-as-you-go)
   - Typical cost: ~$0.01-0.05 per query

3. **Revit & PyRevit**
   - Autodesk Revit 2023, 2024, or 2025
   - PyRevit 4.8.x or higher: https://github.com/pyrevitlabs/pyRevit/releases

## Part 2: Set Up Notion

### Create Standards Database

1. **Create a new Database in Notion**:
   - Name it "BBB Revit Standards"
   - Choose "Table" view

2. **Add these properties**:

   Click "+ Add property" and create each:

   - **Category** (Select)
     - Options: Modeling, Worksets, Views, Families, Documentation, Collaboration, Guardian Rules, General BIM

   - **Studio** (Multi-select)
     - Options: All Studios, Preservation, Museums & Culture, Civic & Urban, Higher Ed, Planning & Analysis

   - **Revit Version** (Multi-select)
     - Options: 2023, 2024, 2025

   - **Status** (Select)
     - Options: Active, Draft, Under Review, Deprecated

   - **Last Updated** (Date)

   - **Owner** (Person)

   - **Keywords** (Multi-select)
     - Add tags like: worksets, levels, views, families, links, sheets, phases, etc.

   - **Priority** (Select)
     - Options: Critical, Important, Reference

3. **Add sample standards** (see Part 5 below)

### Create Notion Integration

1. Go to https://www.notion.so/my-integrations
2. Click "**+ New integration**"
3. Configure:
   - **Name**: Kodama
   - **Logo**: Upload your logo (optional)
   - **Associated workspace**: Select your workspace
   - **Type**: Internal Integration
4. Click "**Submit**"
5. **Copy the "Internal Integration Token"** (starts with `secret_`)
   - ⚠️ Keep this secure! You'll need it later.

### Share Database with Integration

1. Open your "BBB Revit Standards" database in Notion
2. Click "**Share**" (top right)
3. Click "**Invite**"
4. Find and select "**Kodama**" integration
5. Click "**Invite**"

### Get Database ID

1. Open your database in Notion
2. Look at the URL: `https://notion.so/workspace/DATABASE_ID?v=...`
3. Copy the `DATABASE_ID` (32 characters, no dashes)
   - Example: `a8aec43384f447ed84390e8e42c2e089`
   - ⚠️ You'll need this for configuration!

## Part 3: Set Up Anthropic

1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Add billing information (required for API access)
4. Go to "**API Keys**" in the left sidebar
5. Click "**Create Key**"
6. Name it "Kodama"
7. **Copy the API key** (starts with `sk-ant-`)
   - ⚠️ Keep this secure! You won't see it again.

### API Usage & Costs

- **Model**: Claude Sonnet 4 (~$3 per million input tokens)
- **Typical query**: ~1,000-5,000 tokens
- **Estimated cost per query**: $0.003-0.015
- **Monthly estimate** (100 queries): ~$1.50

Set up billing alerts in the Anthropic console to monitor usage.

## Part 4: Install Extension

### Option A: Development Installation

1. **Clone/download this repository**:
   ```powershell
   cd C:\Users\<username>\Code
   git clone <repository-url> bim-standards-chat
   ```

2. **Create symbolic link to PyRevit extensions folder**:
   ```powershell
   # Run PowerShell as Administrator
   $source = "C:\Users\<username>\Code\bim-standards-chat\BBB.extension"
   $target = "$env:APPDATA\pyRevit\Extensions\BBB.extension"
   New-Item -ItemType SymbolicLink -Path $target -Target $source
   ```

### Option B: Direct Installation

1. **Copy the extension folder**:
   - Copy `BBB.extension` folder
   - Paste to: `%APPDATA%\pyRevit\Extensions\`
   
   Full path should be:
   ```
   C:\Users\<username>\AppData\Roaming\pyRevit\Extensions\BBB.extension\
   ```

### Verify Installation

1. Open Windows Explorer
2. Navigate to: `%APPDATA%\pyRevit\Extensions\`
3. Confirm you see `BBB.extension` folder
4. Inside should be:
   - `BBB.tab\`
   - `lib\`
   - `config\`

## Part 5: Configure Extension

### Set API Keys

1. Navigate to: `%APPDATA%\pyRevit\Extensions\BBB.extension\config\`

2. Open `api_keys.json` in a text editor

3. Replace placeholder values:
   ```json
   {
     "notion_api_key": "secret_your_actual_key_from_part2",
     "anthropic_api_key": "sk-ant-your_actual_key_from_part3"
   }
   ```

4. Save the file

⚠️ **Security Note**: This file contains sensitive credentials. Do NOT share or commit to version control.

### Set Notion Database ID

1. Open `config.json` in the same folder

2. Find the `notion` section:
   ```json
   {
     "notion": {
       "database_id": "your-notion-database-id",
       ...
     }
   }
   ```

3. Replace `"your-notion-database-id"` with your actual database ID from Part 2

4. Save the file

### Customize Settings (Optional)

In `config.json`, you can adjust:

- **Search results**: `notion.max_search_results` (default: 5)
- **Response length**: `anthropic.max_tokens` (default: 2048)
- **Creativity**: `anthropic.temperature` (0.0-1.0, default: 0.7)
- **Window size**: `ui.window_width` and `ui.window_height`

## Part 6: Populate Notion Database

Add sample standards to test with:

### Sample Standard 1: Workset Naming Convention

**Title**: Workset Naming Convention  
**Category**: Worksets  
**Studio**: All Studios  
**Status**: Active  
**Priority**: Critical  

**Content**:
```
# Workset Naming Convention

## Overview
Consistent workset naming is critical for coordination and file organization.

## Naming Format
Use this format: `[Discipline]-[Category]-[Sublevel]`

## Examples
- `A-SHELL-EXTERIOR`
- `A-SHELL-INTERIOR`
- `A-INTERIOR-PARTITIONS`
- `A-INTERIOR-DOORS`
- `S-STRUCTURE-COLUMNS`
- `MEP-PLUMBING-FIXTURES`

## Rules
- All caps
- Hyphens for separators (no underscores)
- Discipline prefix first (A, S, MEP)
- Maximum 30 characters
- No special characters except hyphens

## Related Standards
- Link to Model Organization standard
- Link to Guardian Rules
```

### Sample Standard 2: View Template Usage

**Title**: View Template Usage Guidelines  
**Category**: Views  
**Studio**: All Studios  
**Status**: Active  
**Priority**: Important  

**Content**:
```
# View Template Usage

## Overview
View templates ensure consistency and save time.

## When to Use
- All documentation views (plans, sections, elevations)
- Coordination views
- Presentation views

## Standard Templates
- `CD-Floor Plan`
- `CD-Ceiling Plan`
- `CD-Section`
- `CD-Elevation`
- `WIP-Working View`
- `COORD-Coordination View`

## Applying Templates
1. Create view
2. Right-click in Project Browser
3. Apply Template → Choose appropriate template
4. Do NOT override template settings without approval

## Customization
- Never modify base templates
- Create project-specific overrides if needed
- Name overrides: `[Template Name]-[Project]`
```

### Sample Standard 3: Guardian Rules

**Title**: Common Guardian Errors and Solutions  
**Category**: Guardian Rules  
**Studio**: All Studios  
**Status**: Active  
**Priority**: Critical  

**Content**:
```
# Guardian Rules and Error Resolution

## Overview
Guardian checks enforce BBB standards automatically.

## Common Errors

### Duplicate Level Names
**Error**: "Duplicate level name detected"
**Solution**: 
1. Open Section view
2. Find duplicate levels
3. Rename or delete redundant levels
4. Levels must have unique names

### Unplaced Rooms
**Error**: "Rooms not placed or not enclosed"
**Solution**:
1. Turn on Room visibility
2. Find red warning symbol
3. Either place room or delete room tag
4. Check for gaps in room boundaries

### View Template Not Applied
**Error**: "View missing required template"
**Solution**:
1. Right-click view in Project Browser
2. Apply Template
3. Select appropriate CD template
4. Lock template settings

## Getting Help
Contact your studio BIM coordinator if errors persist.
```

Add 5-10 sample standards to test the search functionality.

## Part 7: Test Installation

### Load in Revit

1. **Open Revit** (2023, 2024, or 2025)

2. **Reload PyRevit**:
   - Look for "pyRevit" tab
   - Click "Reload" button
   - Wait for reload to complete

3. **Find BBB Tab**:
   - You should see a new "BBB" tab in the ribbon
   - Inside is "Standards Assistant" panel
   - With "Standards Chat" and "Settings" buttons

### Test Configuration

1. **Click "Settings" button**
   - Dialog should open
   - Click "Yes" to open config folder
   - Verify files are present and correct

2. **Click "Standards Chat" button**
   - Chat window should open
   - Should show welcome message
   - If error appears, check:
     - API keys are correct
     - Database ID is correct
     - Files are not corrupted

### Test Query

Try a simple query:

1. In chat window, type: **"What are the workset naming rules?"**

2. Click **Send** (or press Ctrl+Enter)

3. Expected behavior:
   - "Thinking..." overlay appears
   - Status updates: "Searching Notion database..."
   - Then: "Generating response..."
   - Response appears with answer
   - Sources listed at bottom with clickable links

4. Verify:
   - Response is relevant
   - Sources link to your Notion pages
   - Links open in browser when clicked

### Test Follow-up

Ask a follow-up question:

**"Can you give me an example workset name for interior doors?"**

The assistant should remember context and provide a specific example.

## Part 8: Troubleshooting

### Chat window doesn't open

**Check PyRevit Output**:
1. In Revit, pyRevit tab → Settings → Output Window
2. Look for Python error messages
3. Common issues:
   - Missing config files
   - Syntax errors in JSON files
   - Permission issues

**Fix**:
- Verify all files are in correct locations
- Check JSON files for syntax errors (use jsonlint.com)
- Run Revit as Administrator

### "Configuration file not found"

**Cause**: Extension not in correct location or files missing

**Fix**:
1. Navigate to `%APPDATA%\pyRevit\Extensions\`
2. Confirm `BBB.extension\config\` exists
3. Confirm both `config.json` and `api_keys.json` exist
4. Reload PyRevit

### "API key not configured" or authentication errors

**Cause**: Invalid or placeholder API keys

**Fix**:
1. Open `api_keys.json`
2. Ensure keys:
   - Don't contain "xxxxx" or placeholder text
   - Start with `secret_` (Notion) or `sk-ant-` (Anthropic)
   - Have no extra spaces or quotes
3. Regenerate keys if unsure:
   - Notion: https://www.notion.so/my-integrations
   - Anthropic: https://console.anthropic.com/

### "No standards found" or empty responses

**Cause**: Notion database not accessible or empty

**Fix**:
1. Verify database ID is correct (32 characters, no dashes)
2. Check integration is shared with database (Part 2)
3. Ensure database has pages with Status = "Active"
4. Test Notion API manually: https://developers.notion.com/reference/post-search

### Slow responses

**Causes**: 
- Large Notion pages
- Slow internet
- API rate limiting

**Fix**:
- Reduce `max_search_results` in config.json
- Check internet speed
- Wait between queries

### Links don't open

**Cause**: Browser security or Windows settings

**Fix**:
- Set default browser in Windows Settings
- Check firewall/antivirus isn't blocking
- Try copying link and pasting in browser

## Part 9: Rollout to Team

### Prepare

1. **Document internal standards**:
   - Populate Notion with all standards
   - Review for accuracy and completeness
   - Get approval from BIM leadership

2. **Create distribution package**:
   - Zip the `BBB.extension` folder
   - Include separate instructions
   - Provide pre-configured `config.json` (without API keys)

3. **Set up team API keys**:
   - Create one Notion integration for entire team
   - Create one Anthropic API key for team
   - Or: Create separate keys per studio for usage tracking

### Deploy

**Option A: Central IT Deployment**
- Use network share or deployment tool
- Script installation to all machines
- Pre-configure API keys centrally

**Option B: Self-Service Installation**
- Provide download link + instructions
- Users install to their own machines
- Users request API keys from admins

### Training

1. **Demo session** (30 min):
   - Show how to open chat
   - Example queries
   - How to interpret responses
   - When to click source links

2. **Provide quick reference**:
   - Common questions to ask
   - Keyboard shortcuts
   - Troubleshooting tips

3. **Support channel**:
   - Set up Teams/Slack channel
   - Assign BIM coordinators as first responders
   - Track common issues for FAQ

## Part 10: Maintenance

### Update Standards

1. Edit pages in Notion (no code changes needed)
2. Changes appear immediately in searches
3. Consider versioning strategy for major changes

### Monitor Usage

**Anthropic Console**:
- Review API usage and costs
- Set up billing alerts
- Monitor for unusual patterns

**Notion**:
- Track which standards are accessed most (via manual review)
- Identify gaps in documentation

### Update Extension

To release new version:
1. Make code changes
2. Update version in `__init__.py`
3. Test thoroughly
4. Distribute updated `BBB.extension` folder
5. Users: Replace folder and reload PyRevit

### Gather Feedback

- Survey users quarterly
- Track common questions that get poor responses
- Use feedback to improve Notion content and system prompt

---

## Support

For help with setup:
- Email: dct@bbbarchitects.com (example)
- Teams: BBB DCT Channel
- Slack: #bim-support

## Next Steps

✅ After completing setup:
1. Test with real user questions
2. Iterate on Notion content based on results
3. Train studio BIM coordinators
4. Roll out to pilot group
5. Gather feedback
6. Full deployment

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-14  
**Estimated Setup Time**: 1-2 hours
