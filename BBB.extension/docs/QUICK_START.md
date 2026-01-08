# Quick Start Guide - Kodama

Get up and running in 10 minutes!

## Prerequisites Check

✅ Revit 2023, 2024, or 2025 installed  
✅ PyRevit 4.8+ installed  
✅ Notion workspace access  
✅ Internet connection  

## Step 1: Get API Keys (5 min)

### Notion API Key
1. Go to https://www.notion.so/my-integrations
2. Click "New Integration" → Name it "BBB Standards"
3. Copy the token (starts with `secret_`)

### Anthropic API Key
1. Go to https://console.anthropic.com/
2. Sign up (requires credit card)
3. API Keys → Create Key
4. Copy the key (starts with `sk-ant-`)

## Step 2: Create Notion Database (3 min)

1. In Notion, create new database: "BBB Revit Standards"
2. Add these properties (Select type):
   - **Category** (Select): Modeling, Views, Worksets, etc.
   - **Status** (Select): Active, Draft, Deprecated
   - **Priority** (Select): Critical, Important, Reference
3. Share database with your integration (Share button → Invite integration)
4. Copy database ID from URL (32 character string)

## Step 3: Install Extension (2 min)

1. Copy `BBB.extension` folder
2. Paste to: `%APPDATA%\pyRevit\Extensions\`
3. Result: `%APPDATA%\pyRevit\Extensions\BBB.extension\`

## Step 4: Configure (2 min)

1. Navigate to: `%APPDATA%\pyRevit\Extensions\BBB.extension\config\`

2. Edit `api_keys.json`:
   ```json
   {
     "notion_api_key": "secret_YOUR_KEY_HERE",
     "anthropic_api_key": "sk-ant-YOUR_KEY_HERE"
   }
   ```

3. Edit `config.json` - find `database_id`:
   ```json
   "notion": {
     "database_id": "YOUR_32_CHAR_DATABASE_ID",
   ```

## Step 5: Test (1 min)

1. Open Revit
2. PyRevit tab → Reload
3. Click new **BBB** tab
4. Click **Standards Chat**
5. Ask: "What are the workset naming rules?"

## Expected Result

✅ Chat window opens  
✅ "Thinking..." appears  
✅ Response with answer and sources  
✅ Clickable links to Notion pages  

## Troubleshooting

**Window doesn't open?**
- Check PyRevit Output window for errors
- Verify files are in correct location

**"API key not configured"?**
- Open `api_keys.json` again
- Ensure no placeholder text remains
- Keys should be actual values from APIs

**"No standards found"?**
- Verify database ID is correct
- Check integration has access to database
- Add at least one page with Status = "Active"

## Next Steps

1. Populate Notion with your standards
2. Test with real questions
3. Share with team

## Need Help?

See `SETUP_GUIDE.md` for detailed instructions.

---

**Total Time**: ~10 minutes  
**Cost**: Free tier Anthropic (~$5 credit) or ~$0.01 per query  
**Support**: Contact DCT Team
