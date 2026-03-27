# 📋 Automation Debugging Steps

## Quick Start: Follow These Steps

### Step 1: Check Terminal Output (MOST IMPORTANT!)

When you click "▶️ Start", **watch the terminal** where the GUI is running.

**Expected output:**
```
INFO - 🚀 Starting automation with 1 profiles
INFO -    - Max instances: 10
INFO -    - Desktop searches: 33
INFO -    - Mobile searches: 23
INFO - 📍 run_automation() called
INFO - 📦 Importing modules...
INFO - ✓ Imports successful
INFO - 📂 Loading 1 profiles...
INFO -   ✓ Loaded: 1 (Isolated)
INFO - ✓ Loaded 1 profiles
INFO - ⚙️ Getting options...
INFO - ✓ Options: desktop=33, mobile=23
INFO - 📝 Creating word generator...
INFO - ✓ Word generator ready
INFO - Starting concurrent searches...
```

**If you see NONE of this:**
- ❌ Thread is not starting
- ❌ Check browser console for JavaScript errors

**If you see SOME of this then it stops:**
- ❌ Something is failing midway
- ❌ Look for error messages after the last INFO line

---

### Step 2: Check Browser Console

1. Press **F12**
2. Go to **Console** tab
3. Click "▶️ Start"

**Look for errors like:**
```javascript
Failed to start automation
TypeError: ...
Network error: ...
```

**Screenshot and report any errors!**

---

### Step 3: Test Imports

Open Python and run:
```python
from bing_rewards.app import execute_searches_for_instance, word_generator
from bing_rewards.options import get_options
print("✓ Imports work!")
```

**If this fails:**
- ❌ Import error - we need to fix the import path

**If this succeeds:**
- ✅ Imports are working

---

### Step 4: Run Minimal Test

I'll create a test script for you. Run this:

```bash
python -m bing_rewards.gui
```

Then:
1. Select 1 profile
2. Set Desktop Searches: **2**
3. Set Mobile Searches: **1**
4. Click "▶️ Start"
5. **Watch the terminal closely**

**What happens?**
- Does browser launch?
- Do searches execute?
- Any errors in terminal?

---

## 🐛 Common Issues & Fixes

### Issue 1: Nothing Happens When Clicking Start

**Symptoms:**
- No terminal output
- Browser doesn't launch
- Event Log shows "Failed to start automation"

**Possible causes:**
1. JavaScript error preventing API call
2. Backend thread not starting
3. Silent exception in thread startup

**How to debug:**
1. Check browser console (F12)
2. Look for errors before "Failed to start"
3. Add logging to see if thread starts

---

### Issue 2: Browser Launches But No Searches

**Symptoms:**
- Browser opens
- Login page shows
- No searches execute
- Eventually times out

**Possible causes:**
1. `execute_searches_for_instance()` failing
2. Word generator not working
3. Options not configured correctly

**How to debug:**
1. Check terminal for error after browser launches
2. Look for "Starting concurrent searches..." message
3. Add logging inside execute_searches_for_instance

---

### Issue 3: Immediate Error Message

**Symptoms:**
- Click "Start"
- Immediate "Failed to start" error
- Terminal shows exception

**Possible causes:**
1. Import error
2. Profile loading error
3. Controller initialization error

**How to debug:**
1. **Copy the EXACT error message**
2. Check which step failed (from logging)
3. Fix that specific issue

---

## 🔧 What I Need From You

Please provide:

### 1. Terminal Output (Full)

```
Copy EVERYTHING that appears in terminal when you click "Start"
From: "Starting automation with..."
To: Last error message or "Automation completed"
```

### 2. Browser Console Errors

```
Press F12 → Console
Click "Start"
Copy all red error messages
```

### 3. What You See

**Answer these questions:**

1. **Does browser launch?** (Yes/No)
2. **Do searches execute?** (Yes/No)
3. **Any error messages?** (Copy/paste)
4. **How many profiles selected?** (Number)
5. **What are your settings?**
   - Desktop Searches: ?
   - Mobile Searches: ?
   - Max Instances: ?

---

## 🎯 Next Actions

Based on what you report, I'll:

1. **Add detailed logging** to pinpoint exact failure
2. **Create test scripts** to isolate the issue
3. **Fix the specific problem** once identified
4. **Test together** to confirm it works

---

## 📞 Quick Report Template

Copy and fill this out:

```
=== AUTOMATION DEBUG REPORT ===

Terminal Output:
[Paste terminal output here]

Browser Console Errors:
[Paste browser console errors here]

Observations:
- Browser launches: [Yes/No]
- Searches execute: [Yes/No]
- Error messages: [Yes/No - paste if yes]

Settings Used:
- Profiles selected: [Number]
- Desktop Searches: [Number]
- Mobile Searches: [Number]
- Max Instances: [Number]

Additional Notes:
[Anything else you noticed]

=== END REPORT ===
```

---

**Let's fix this!** 🚀
