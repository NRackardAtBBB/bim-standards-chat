# Quick Start: Vector Search Installation

## Step 1: Install Python and Packages

**pyRevit can use an external Python installation** via the cpython engine. This is much simpler than installing into pyRevit's embedded Python.

### 1a. Install Python 3.12.3 (64-bit)

1. Download **Python 3.12.3 Windows x86-64 executable installer** from [python.org/downloads](https://www.python.org/downloads/release/python-3123/)
2. Run the installer
3. **IMPORTANT:** Check the box "Add Python to PATH"
4. Complete the installation

### 1b. Verify Python Installation

```powershell
# Check Python version (should be 3.12.3)
python --version

# Check pip version
pip --version
```

### 1c. Install Required Packages

```powershell
pip install chromadb openai tiktoken
```

This will take a few minutes as it downloads and installs all dependencies.

### 1d. Find Your site-packages Path

```powershell
python -c "import site; print(site.getsitepackages()[0])"
```

Copy this path - you'll need it in Step 2. It will look something like:
```
C:\Users\nrackard\AppData\Local\Programs\Python\Python312\Lib\site-packages
```

### 1e. Verify Installation

```powershell
pip list | Select-String "chromadb|openai|tiktoken"
```

You should see all three packages listed.

## Step 2: Verify Code Configuration

The [vector_db_client.py](BBB.extension/lib/standards_chat/vector_db_client.py) file is already configured to use cpython:

- **Line 1:** `#! python3` - Tells pyRevit to use cpython engine
- **Lines 13-24:** Auto-detects Python site-packages paths

You don't need to modify anything unless the auto-detection fails. If you get import errors, uncomment lines 16-17 in vector_db_client.py and add your specific paths from Step 1d.

## Step 3: Configure Your OpenAI API Key

Copy the template and add your key (do not commit `api_keys.json`):

1. Copy [BBB.extension/config/api_keys.example.json](BBB.extension/config/api_keys.example.json) to `BBB.extension/config/api_keys.json`
2. Update the `openai_api_key` value:
```json
{
  "openai_api_key": "sk-proj-YOUR_KEY_HERE"
}
```

## Step 4: Enable the Feature

Your username (`nrackard`) is already whitelisted in [config.json](BBB.extension/config/config.json).

To enable:
1. Open Kodama in Revit
2. Click Settings
3. Check "Enable semantic search (Developer Preview)"
4. The vector search section will appear
5. Click "Sync SharePoint to Vector Database"
6. Wait for sync to complete (~2-3 minutes for 45 pages)
7. Click Save

## Step 5: Test It

1. Open Kodama chat
2. Ask a question like "How do I create door families?"
3. The status will show "Performing semantic search..." instead of "Searching..."
4. Results will be more conceptually relevant

## What to Expect

### Before (Keyword Search)
- Matches exact words only
- Misses synonyms and related concepts
- Example: "door" doesn't find "entry" or "opening"

### After (Semantic Search)
- Understands meaning and context
- Finds conceptually similar content
- Example: "door" also finds "entry," "threshold," "access point"

## Troubleshooting

### "Import chromadb could not be resolved"

**Option A: Verify installation**
```powershell
pip list | Select-String "chromadb|openai|tiktoken"
```

**Option B: Manually set paths in vector_db_client.py**

Find your site-packages path:
```powershell
python -c "import site; print(site.getsitepackages()[0])"
```

Then edit [vector_db_client.py](BBB.extension/lib/standards_chat/vector_db_client.py) lines 16-17:
```python
sys.path.append(r'C:\Users\nrackard\AppData\Local\Programs\Python\Python312\Lib\site-packages')
sys.path.append(r'C:\Users\nrackard\AppData\Local\Programs\Python\Python312\Lib')
```

**Option C: Python version mismatch**

Verify Python version matches:
```powershell
python --version  # Should be 3.12.3
```

If different, install Python 3.12.3 specifically.

### "OpenAI API key invalid"
- Check [api_keys.json](BBB.extension/config/api_keys.json)
- Verify key starts with `sk-proj-`
- Test at https://platform.openai.com/api-keys

### "Access Denied" in Settings
- Verify your username in `vector_search.developer_whitelist`
- Check spelling (case-insensitive)
- Windows username: `$env:USERNAME` in PowerShell

### Sync Takes Too Long
- Normal: 2-5 minutes for 45 pages
- Generating embeddings is slow but only done once
- Progress updates show current status

## Next Steps

Once working:
1. Use it for a few days
2. Compare results quality vs keyword search
3. Gather feedback before deploying to team
4. Consider adding more users to whitelist

## Full Documentation

See [VECTOR_SEARCH.md](VECTOR_SEARCH.md) for complete technical details.
