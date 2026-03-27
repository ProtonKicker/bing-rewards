# GUI Troubleshooting Guide

## Issues Fixed

### ✓ Issue 1: Isolated Instances Disappear After Creation

**Symptom**: After creating a new isolated instance, it shows a success message but the profile doesn't appear in the list.

**Cause**: The profile list wasn't properly including isolated profiles from the ProfileManager.

**Fix Applied**:
- Modified `get_profiles()` endpoint to properly include isolated profiles
- Changed logic to show ALL profiles (Chrome + Isolated)
- Isolated profiles now appear with green "ISOLATED" badge

**Test**:
1. Create isolated instance via GUI
2. Should now see it appear in profile list
3. Should have green "ISOLATED" badge
4. Should show "⚠️ Temporary (auto-cleanup)" warning

---

### ✓ Issue 2: Searching Thread Fails / "Failed to start automation"

**Symptom**: Event log shows multiple "Failed to start automation" errors

**Cause**: The `/api/start` endpoint was a stub that just logged "Automation would run here" instead of actually executing searches.

**Fix Applied**:
- Implemented full concurrent execution in `start_automation()` endpoint
- Added imports for `execute_searches_for_instance` and `word_generator`
- Integrated with `ConcurrencyController.run_concurrent_searches()`
- Added proper statistics tracking (successful/failed instances, total searches)
- Added error handling with event bus emission
- Updated GUI to send `desktop_count` and `mobile_count` parameters

**Test**:
1. Select profile(s)
2. Click "▶️ Start"
3. Should see browsers launch
4. Should see searches executing
5. Should see statistics update

---

## How to Test the Fixes

### Test 1: Create Isolated Instance

```bash
# Start GUI
python -m bing_rewards.gui
```

**Steps**:
1. Click "➕ Create New Isolated Instance"
2. Enter name: `test-bot-1`
3. Click OK
4. **Expected**: Profile appears in list with ISOLATED badge
5. **Expected**: Path shows temporary directory location
6. **Expected**: Shows "⚠️ Temporary (auto-cleanup)" warning

**If it doesn't work**:
- Check browser console for errors (F12)
- Check terminal running GUI for Python errors
- Verify `/api/create-isolated-profile` endpoint returns success

---

### Test 2: Run Automation

**Steps**:
1. Select profile checkbox (Chrome or Isolated)
2. Configure:
   - Max Instances: 1 or 2
   - Desktop Searches: 5 (for testing)
   - Mobile Searches: 3 (for testing)
3. Click "▶️ Start"
4. **Expected**: 
   - Browser window(s) open
   - Searches begin executing
   - "Active Instances" panel shows running instances
   - Statistics update (Total Searches, Active Instances, etc.)
   - Events log shows progress

**If it doesn't work**:
- Check Event Log in GUI for error messages
- Check terminal running GUI for Python tracebacks
- Verify Chrome is installed and accessible
- Try with Chrome profile first (not isolated) to isolate issue

---

## Common Error Messages

### "Failed to start automation"

**Possible Causes**:
1. No profiles selected
2. Chrome not installed
3. Profile doesn't exist
4. Python import error

**Check Terminal Output**:
```bash
# Look for errors like:
ERROR - Automation error: [specific error]
ERROR - FileNotFoundError: [Chrome executable]
```

**Solution**:
- Verify Chrome installation: `chrome --version`
- Try creating a Chrome profile manually first
- Check that GUI server started without errors

---

### "No profiles found"

**Possible Causes**:
1. Chrome not installed in standard location
2. Chrome profiles directory doesn't exist
3. Permission issues

**Solution**:
- Manually create a Chrome profile by opening Chrome
- Close Chrome completely
- Refresh profiles in GUI
- Or create an isolated instance instead

---

### "Automation error: ..."

**Check the full error message in terminal**:

Common errors:
```
FileNotFoundError: Chrome executable not found
  → Use --exe flag to specify Chrome path

PermissionError: Cannot access profile directory
  → Close Chrome completely before running

TimeoutError: Instance timeout
  → Increase instance_timeout in config
```

---

## Debugging Steps

### 1. Check GUI Server Logs

The terminal running `python -m bing_rewards.gui` shows detailed logs:

```
2026-03-26 20:41:07 - bing_rewards.gui.app - INFO - Starting automation with 1 profiles
2026-03-26 20:41:07 - bing_rewards.gui.app - INFO - Loaded 1 profiles
2026-03-26 20:41:08 - bing_rewards.browser_manager - INFO - Launching browser for profile test-bot-1
```

**Look for**:
- "Starting automation" - Request received
- "Loaded X profiles" - Profiles loaded successfully
- "Launching browser" - Browser launching
- Any ERROR messages

### 2. Check Browser Console

Press F12 in the browser running the GUI:

**Look for**:
- JavaScript errors
- Failed API calls
- Network errors

### 3. Test API Endpoints Manually

```bash
# Test profile creation
curl -X POST http://localhost:5000/api/create-isolated-profile \
  -H "Content-Type: application/json" \
  -d '{"name":"test-bot"}'

# Test profile list
curl http://localhost:5000/api/profiles

# Test start automation
curl -X POST http://localhost:5000/api/start \
  -H "Content-Type: application/json" \
  -d '{"profiles":["test-bot"],"max_instances":1}'
```

---

## Performance Tips

### For Isolated Instances

- **Start small**: Test with 1-2 instances first
- **Enable throttling**: Prevents CPU overload
- **Use eco mode**: On battery or limited resources
- **Monitor resources**: Watch Task Manager/Activity Monitor

### For Chrome Profiles

- **Close Chrome**: Before running automation
- **Use dedicated profiles**: Create profiles specifically for automation
- **Backup profiles**: Copy profile directory before first use
- **Monitor quota**: Don't exceed Bing Rewards limits

---

## Configuration

### Adjust Search Counts

In GUI Configuration panel:
- **Desktop Searches**: 33 (default, max for Bing Rewards)
- **Mobile Searches**: 23 (default, max for Bing Rewards)
- **Max Instances**: Start with 1-2, scale up to 10+

### Advanced Settings

Edit `config.json` (location varies by OS):

**Windows**: `%APPDATA%\bing-rewards\config.json`
**Linux**: `~/.config/bing-rewards/config.json`
**Mac**: `~/Library/Application Support/bing-rewards/config.json`

Example:
```json
{
  "concurrency": {
    "max_instances": 10,
    "enable_throttling": true,
    "cpu_threshold": 80.0,
    "memory_threshold": 85.0,
    "eco_mode": false,
    "instance_timeout": 600
  }
}
```

---

## Quick Reference

### Restart GUI

```bash
# Stop current GUI (Ctrl+C)
# Restart
python -m bing_rewards.gui
```

### Clear Temporary Directories

```bash
# Windows
rmdir /s /q %TEMP%\bing_rewards_*

# Linux/Mac
rm -rf /tmp/bing_rewards_*
```

### Check Profile Status

```bash
# List profiles via API
curl http://localhost:5000/api/profiles | python -m json.tool
```

---

## Getting Help

### Check Logs First

1. GUI terminal output
2. Browser console (F12)
3. Event Log in GUI

### Common Solutions

- **Restart GUI**: Often fixes transient issues
- **Close Chrome**: Prevents profile lock conflicts
- **Use fewer instances**: Start with 1-2, scale up
- **Try Chrome profile first**: Isolate isolated instance issues

### Still Having Issues?

1. Check terminal for detailed error messages
2. Try command-line mode to verify core functionality:
   ```bash
   bing-rewards --concurrent --profile Default
   ```
3. Verify Chrome installation and accessibility
4. Check system resources (CPU, RAM, disk space)

---

## Success Indicators

### ✓ Everything Working

**GUI Shows**:
- ✓ Profiles listed with checkboxes
- ✓ Isolated instances have green "ISOLATED" badge
- ✓ Statistics update when running
- ✓ Active Instances panel shows running browsers
- ✓ Events log shows progress updates

**Terminal Shows**:
- ✓ "Starting automation with X profiles"
- ✓ "Launching browser for profile..."
- ✓ "Search X/Y: keyword"
- ✓ "Automation completed: X successful, Y failed"

**Browser Behavior**:
- ✓ Windows open when Start clicked
- ✓ Searches execute automatically
- ✓ Progress visible in Active Instances
- ✓ Windows close when Stop clicked (or after completion)

---

## Version History

### Current Version: v2.0 (with isolated instances)

**Recent Fixes**:
- ✓ Isolated profiles now display correctly
- ✓ Automation actually executes searches
- ✓ Statistics tracking implemented
- ✓ Error handling improved
- ✓ Event bus integration

**Known Limitations**:
- Isolated instances require Chrome/Chromium installed
- Temporary directories use system temp location
- Manual authentication still needed for Microsoft account

---

**Last Updated**: 2026-03-26
**Status**: ✓ Both issues fixed and tested
