# Testing Checklist - Kodama

Use this checklist to verify the extension is working correctly.

## Pre-Testing Setup

### Configuration
- [ ] `api_keys.json` has valid Notion API key
- [ ] `api_keys.json` has valid Anthropic API key
- [ ] `config.json` has correct Notion database ID
- [ ] Notion integration is shared with database
- [ ] Database has at least 3 pages with Status = "Active"

### Installation
- [ ] `BBB.extension` folder is in `%APPDATA%\pyRevit\Extensions\`
- [ ] All subfolders are present (BBB.tab, lib, config)
- [ ] All Python files are present in `lib/standards_chat/`
- [ ] XAML file exists at `lib/ui/chat_window.xaml`
- [ ] Config files exist in `config/` folder

### Environment
- [ ] Revit 2023, 2024, or 2025 is installed
- [ ] PyRevit 4.8+ is installed and loaded
- [ ] Internet connection is active
- [ ] Firewall allows HTTPS connections

## Test 1: Extension Loading

**Steps:**
1. Open Revit
2. Reload PyRevit (pyRevit tab → Reload)
3. Check for BBB tab in ribbon

**Expected Results:**
- [ ] BBB tab appears in ribbon
- [ ] "Standards Assistant" panel is visible
- [ ] "Standards Chat" button exists
- [ ] "Settings" button exists
- [ ] No errors in PyRevit output window

**If Failed:**
- Check PyRevit output window for errors
- Verify extension folder structure
- Try running Revit as Administrator

## Test 2: Settings Dialog

**Steps:**
1. Click "Settings" button
2. Read dialog message
3. Click "Yes" to open folder

**Expected Results:**
- [ ] Dialog opens without errors
- [ ] Message shows correct config folder path
- [ ] "Yes" opens Windows Explorer
- [ ] Explorer shows config folder with both JSON files

**If Failed:**
- Check script.py in Settings.pushbutton
- Verify config folder exists

## Test 3: Chat Window Opening

**Steps:**
1. Click "Standards Chat" button
2. Wait for window to appear

**Expected Results:**
- [ ] Chat window opens within 2 seconds
- [ ] Window title is "Kodama"
- [ ] Welcome message is visible
- [ ] Input box is present at bottom
- [ ] Send button is present and enabled
- [ ] Header shows "Ready" status

**If Failed:**
- Check PyRevit output for errors
- Verify XAML file exists and is valid
- Check that chat_window.py has no syntax errors
- Verify API keys are configured (even if invalid)

## Test 4: Basic Query

**Steps:**
1. Type in input box: "What are the workset naming rules?"
2. Click Send (or press Ctrl+Enter)

**Expected Results:**
- [ ] Input box clears
- [ ] User message appears (blue bubble, right-aligned)
- [ ] Loading overlay appears ("Thinking...")
- [ ] Status updates to "Searching Notion database..."
- [ ] Status updates to "Generating response..."
- [ ] Assistant response appears (white bubble, left-aligned)
- [ ] Response is relevant to question
- [ ] "Sources" section appears at bottom
- [ ] Source links are clickable
- [ ] Loading overlay disappears
- [ ] Input box re-enables and gets focus
- [ ] Total time: 2-10 seconds

**If Failed:**
- Check API keys are valid (test in Notion/Anthropic web interfaces)
- Check internet connection
- Look for error message in chat
- Check PyRevit output for exceptions

## Test 5: Source Links

**Steps:**
1. After getting a response with sources
2. Click on a source link

**Expected Results:**
- [ ] Browser opens
- [ ] Notion page loads
- [ ] Page is one of your standards pages
- [ ] Page content matches what was referenced

**If Failed:**
- Check default browser is set in Windows
- Try copying link and pasting manually
- Verify Notion pages are accessible

## Test 6: Follow-up Question

**Steps:**
1. After first query, ask: "Can you give me an example?"
2. Click Send

**Expected Results:**
- [ ] Response is contextually relevant to previous question
- [ ] Assistant references previous conversation
- [ ] Example is specific and accurate

**If Failed:**
- Check conversation_history logic in anthropic_client.py
- Verify messages are being stored correctly

## Test 7: Context-Aware Query

**Steps:**
1. In Revit, open a Floor Plan view
2. Select some elements
3. In chat, ask: "What view template should I use?"

**Expected Results:**
- [ ] Response considers that you're in a floor plan
- [ ] May reference your current view in the answer
- [ ] Provides relevant view template suggestion

**If Failed:**
- Context extraction is optional/best-effort
- May not always include context in response
- Check utils.py extract_revit_context() function

## Test 8: Error Handling

**Steps:**
1. Temporarily change API key to invalid value
2. Reload PyRevit
3. Try to send a message

**Expected Results:**
- [ ] Error message appears in chat
- [ ] Message is user-friendly (not raw exception)
- [ ] Application doesn't crash
- [ ] Can close window and reopen

**If Failed:**
- Check try/except blocks in chat_window.py
- Verify error messages are defined

## Test 9: No Results Query

**Steps:**
1. Ask something completely off-topic: "What's the weather?"

**Expected Results:**
- [ ] Response acknowledges standards don't cover this
- [ ] No error or crash
- [ ] Polite message suggesting what assistant can help with

**If Failed:**
- Check system prompt in config.json
- Review Claude's behavior with irrelevant queries

## Test 10: Multiple Windows

**Steps:**
1. Open Standards Chat
2. Click Standards Chat button again
3. Try interacting with both windows

**Expected Results:**
- [ ] Second window opens
- [ ] Both windows function independently
- [ ] Can send messages in both
- [ ] No cross-talk or interference

**If Failed:**
- This is expected behavior (current design)
- Could implement singleton pattern if needed

## Test 11: Keyboard Shortcuts

**Steps:**
1. Type a message
2. Press Enter (without Ctrl)
3. Type another message
4. Press Ctrl+Enter

**Expected Results:**
- [ ] Enter alone creates new line
- [ ] Ctrl+Enter sends message
- [ ] Message sends correctly

**If Failed:**
- Check KeyDown event handler in chat_window.py

## Test 12: Long Response

**Steps:**
1. Ask: "Can you explain all the view template best practices in detail?"

**Expected Results:**
- [ ] Response generates successfully
- [ ] Long response displays correctly
- [ ] Scrolling works in message area
- [ ] No truncation or formatting issues
- [ ] Sources still visible at bottom

**If Failed:**
- Check max_tokens setting in config.json
- Verify TextBlock wrapping in XAML
- Check ScrollViewer configuration

## Test 13: Special Characters

**Steps:**
1. Ask question with special characters: "What about A-SHELL-001 & A-SHELL-002?"

**Expected Results:**
- [ ] Characters display correctly in user message
- [ ] Response handles characters properly
- [ ] No encoding errors

**If Failed:**
- Check UTF-8 encoding in file reads/writes
- Verify string handling in API calls

## Test 14: Rapid Queries

**Steps:**
1. Send first query
2. Immediately send second query (before first completes)
3. Wait for both to complete

**Expected Results:**
- [ ] Both queries process
- [ ] Responses appear in order
- [ ] No crashes or deadlocks
- [ ] UI remains responsive

**If Failed:**
- Rate limiting may delay second query
- Check threading implementation
- May be acceptable behavior

## Test 15: Window Closing

**Steps:**
1. Open chat window
2. Send a query
3. Close window while query is processing
4. Reopen chat window

**Expected Results:**
- [ ] Window closes without error
- [ ] Background thread terminates
- [ ] Can reopen window successfully
- [ ] New window starts fresh (no old state)

**If Failed:**
- Check thread.IsBackground = True
- Verify window cleanup

## Performance Benchmarks

Measure and record:

- [ ] Window open time: _____ seconds (target: <2s)
- [ ] First query response time: _____ seconds (target: 3-7s)
- [ ] Subsequent query time: _____ seconds (target: 2-5s)
- [ ] Memory usage increase: _____ MB (target: <100MB)
- [ ] No memory leaks after 10 queries

## User Acceptance Tests

Have 3-5 test users try these scenarios:

### Scenario 1: New User
- [ ] Can find and open chat without help
- [ ] Understands how to ask questions
- [ ] Finds responses helpful
- [ ] Can navigate to source documentation

### Scenario 2: Common Question
- [ ] Ask: "How do I organize worksets?"
- [ ] Response is accurate and complete
- [ ] Sources are relevant
- [ ] Takes less than 1 minute total

### Scenario 3: Complex Question
- [ ] Ask: "What's the difference between view templates and view filters?"
- [ ] Response explains both concepts
- [ ] Shows how they relate
- [ ] Provides examples

### Scenario 4: Error Recovery
- [ ] Intentionally ask unclear question
- [ ] Assistant asks for clarification or provides best answer
- [ ] User can rephrase and get better answer

### Scenario 5: Daily Use
- [ ] Use for 1 week in daily work
- [ ] Report: Did it save time?
- [ ] Report: Were answers accurate?
- [ ] Report: Would you recommend to colleagues?

## Final Checks

Before deploying to production:

- [ ] All tests above pass
- [ ] User acceptance criteria met
- [ ] Documentation is complete and accurate
- [ ] API keys are secured
- [ ] Support process is defined
- [ ] Rollback plan is documented
- [ ] Team training is scheduled

## Known Issues

Document any issues found but not blocking:

1. Issue: ________________________________
   Workaround: __________________________
   Priority: Low / Medium / High

2. Issue: ________________________________
   Workaround: __________________________
   Priority: Low / Medium / High

## Test Environment

- **Date Tested**: _______________
- **Tester**: _______________
- **Revit Version**: _______________
- **PyRevit Version**: _______________
- **Windows Version**: _______________
- **Test Database Pages**: _______________
- **Overall Result**: ⬜ Pass / ⬜ Fail

## Sign-off

- [ ] All critical tests pass
- [ ] Known issues documented
- [ ] Ready for pilot deployment

**Tester Signature**: _________________  
**Date**: _________________

---

**Next Step**: If all tests pass, proceed to pilot deployment per SETUP_GUIDE.md
