# 🔍 TODO: Debug Automation Failure

## Problem Statement

**Issue:** Automation fails to start when clicking "▶️ Start" button

**Symptoms:**
- Browser launches successfully ✅
- Login works (manual login possible) ✅
- Profile creation and display work ✅
- **BUT** searches don't execute ❌
- Event Log shows: `"ERROR: Failed to start automation"`

---

## 📋 Debugging Checklist

### Phase 1: Check Terminal Logs

**What to look for:**
```bash
# When you click "Start", check terminal for:
- Import errors
- Exception tracebacks
- "Automation would run here" message (old code)
- Any error messages
```

**Expected vs Actual:**

| Expected | Actual |
|----------|--------|
| `Starting automation with X profiles` | ? |
| `Loaded X profiles` | ? |
| `Executing searches...` | ? |
| `Automation completed` | ? |

**Action:**
1. Start GUI: `python -m bing_rewards.gui`
2. Watch terminal output
3. Click "Start"
4. **Copy ALL terminal output**

---

### Phase 2: Check Browser Console

**What to look for:**
- JavaScript errors
- Failed API calls
- Network errors

**How to check:**
1. Press **F12** to open DevTools
2. Go to **Console** tab
3. Click "Start" button
4. **Screenshot or copy errors**

**Expected:**
```javascript
// No errors
```

**Actual:**
```javascript
// ??? (Check and report)
```

---

### Phase 3: Test API Directly

**Test the `/api/start` endpoint:**

Open browser console (F12) and run:
```javascript
fetch('/api/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        profiles: ['1'],  // Use your profile name
        max_instances: 2,
        eco_mode: false,
        desktop_count: 5,
        mobile_count: 3,
        no_throttle: false
    })
})
.then(r => r.json())
.then(console.log)
.catch(console.error)
```

**Expected response:**
```json
{
  "status": "started",
  "profiles": ["1"]
}
```

**Actual response:**
```json
// ??? (Run and check)
```

---

### Phase 4: Check Code Execution Path

**Current code in `gui/app.py`:**

```python
@app.route("/api/start", methods=["POST"])
def start_automation():
    # ... validation ...
    
    def run_automation():
        try:
            from bing_rewards.app import execute_searches_for_instance, word_generator
            from bing_rewards.options import get_options
            
            # Load profiles
            profile_configs = []
            for profile_name in profiles:
                profile = gui_state["profile_manager"].get_profile(profile_name)
                if not profile:
                    profile = ProfileConfig(profile_name=profile_name)
                    gui_state["profile_manager"].add_profile(profile)
                profile_configs.append(profile)

            logger.info(f"Loaded {len(profile_configs)} profiles")

            # Get options
            options = get_options()
            options.desktop_count = desktop_count
            options.mobile_count = mobile_count

            # Word generator factory
            def words_gen_factory():
                return word_generator()

            # Execute searches ← SHOULD HAPPEN HERE
            results = gui_state["controller"].run_concurrent_searches(
                profiles=profile_configs,
                words_gen_factory=words_gen_factory,
                search_executor=lambda inst, wg: execute_searches_for_instance(
                    inst, wg, options, desktop_count, mobile_count
                ),
                options=options,
            )
            
            # Update statistics
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            total_searches = sum(r.searches_completed for r in results)

            gui_state["statistics"]["successful_instances"] = successful
            gui_state["statistics"]["failed_instances"] = failed
            gui_state["statistics"]["total_searches"] = total_searches

            logger.info(f"Automation completed: {successful} successful, {failed} failed")

        except Exception as e:
            logger.error(f"Automation error: {e}", exc_info=True)
            gui_state["event_bus"].emit(
                EventType.INSTANCE_ERROR,
                source="GUI",
                profile_name="SYSTEM",
                data={"error": str(e)},
            )
        finally:
            gui_state["is_running"] = False
            gui_state["controller"] = None

    thread = threading.Thread(target=run_automation, daemon=True)
    thread.start()

    return jsonify({"status": "started", "profiles": profiles})
```

**Questions to answer:**

1. **Does the thread start?**
   - Add: `logger.info("Thread started")` after `thread.start()`
   - Check terminal output

2. **Does `run_automation()` execute?**
   - Add: `logger.info("run_automation called")` at start of function
   - Check terminal output

3. **Do imports work?**
   - Try importing manually in Python:
   ```python
   from bing_rewards.app import execute_searches_for_instance, word_generator
   from bing_rewards.options import get_options
   print("✓ Imports work")
   ```

4. **Does `run_concurrent_searches()` execute?**
   - Add logging before and after the call
   - Check if it hangs or throws error

---

### Phase 5: Minimal Test Case

**Create a minimal test script:**

Save as `test_automation.py`:
```python
#!/usr/bin/env python3
"""Test automation with minimal config."""

from bing_rewards.profile_config import ProfileManager
from bing_rewards.gui.app import gui_state
from bing_rewards.app import execute_searches_for_instance, word_generator
from bing_rewards.options import get_options

print("=" * 70)
print("MINIMAL AUTOMATION TEST")
print("=" * 70)

# Get a profile
pm = gui_state["profile_manager"]
profiles = pm.get_active_profiles()

if not profiles:
    print("❌ No profiles found!")
    exit(1)

# Use first isolated profile
profile = None
for p in profiles:
    if p.is_isolated:
        profile = p
        break

if not profile:
    print("❌ No isolated profiles found!")
    exit(1)

print(f"✓ Using profile: {profile.profile_name}")
print(f"✓ Path: {profile.user_data_dir}")

# Get options
options = get_options()
options.desktop_count = 2
options.mobile_count = 1

# Word generator
def words_gen_factory():
    return word_generator()

print("✓ Starting automation test...")

try:
    # Try to execute searches for this single profile
    from bing_rewards.browser_manager import BrowserInstance
    
    instance = BrowserInstance(profile=profile.profile_name)
    wg = words_gen_factory()
    
    print("✓ Executing searches...")
    result = execute_searches_for_instance(instance, wg, options, 2, 1)
    
    print(f"✓ Result: {result}")
    print(f"  - Success: {result.success}")
    print(f"  - Searches: {result.searches_completed}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("=" * 70)
```

**Run it:**
```bash
python test_automation.py
```

**Expected:**
- Browser launches
- Searches execute
- Result printed

**Actual:**
- ??? (Run and report)

---

### Phase 6: Check ConcurrencyController

**Test the controller directly:**

Save as `test_controller.py`:
```python
#!/usr/bin/env python3
"""Test ConcurrencyController."""

from bing_rewards.profile_config import ProfileManager, ProfileConfig
from bing_rewards.gui.app import gui_state
from bing_rewards.app import execute_searches_for_instance, word_generator
from bing_rewards.options import get_options
from bing_rewards.gui.concurrency_controller import ConcurrencyController, ConcurrencyConfig
from bing_rewards.event_bus import EventBus

print("=" * 70)
print("CONTROLLER TEST")
print("=" * 70)

# Get profiles
pm = gui_state["profile_manager"]
profiles = pm.get_active_profiles()
isolated_profiles = [p for p in profiles if p.is_isolated]

if not isolated_profiles:
    print("❌ No isolated profiles found!")
    exit(1)

print(f"✓ Found {len(isolated_profiles)} isolated profiles")

# Create controller
config = ConcurrencyConfig(
    max_instances=2,
    enable_throttling=True,
    eco_mode=False,
)

event_bus = EventBus()
controller = ConcurrencyController(config=config, event_bus=event_bus)

print("✓ Controller created")

# Get options
options = get_options()
options.desktop_count = 2
options.mobile_count = 1

# Word generator factory
def words_gen_factory():
    return word_generator()

print("✓ Starting concurrent searches...")

try:
    results = controller.run_concurrent_searches(
        profiles=isolated_profiles[:1],  # Just 1 profile for testing
        words_gen_factory=words_gen_factory,
        search_executor=lambda inst, wg: execute_searches_for_instance(
            inst, wg, options, 2, 1
        ),
        options=options,
    )
    
    print(f"✓ Results: {results}")
    for r in results:
        print(f"  - {r.profile_name}: {r.searches_completed} searches, success={r.success}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("=" * 70)
```

**Run it:**
```bash
python test_controller.py
```

---

### Phase 7: Add Detailed Logging

**Modify `gui/app.py` to add logging:**

```python
@app.route("/api/start", methods=["POST"])
def start_automation():
    """Start concurrent automation."""
    if gui_state["is_running"]:
        return jsonify({"error": "Already running"}), 400

    data = request.json
    profiles = data.get("profiles", [])
    max_instances = data.get("max_instances", 10)
    eco_mode = data.get("eco_mode", False)
    desktop_count = data.get("desktop_count", 33)
    mobile_count = data.get("mobile_count", 23)

    if not profiles:
        return jsonify({"error": "No profiles selected"}), 400

    logger.info(f"🚀 Starting automation with {len(profiles)} profiles")
    logger.info(f"   - Max instances: {max_instances}")
    logger.info(f"   - Desktop searches: {desktop_count}")
    logger.info(f"   - Mobile searches: {mobile_count}")

    # Create controller
    config = ConcurrencyConfig(
        max_instances=max_instances,
        enable_throttling=not data.get("no_throttle", False),
        eco_mode=eco_mode,
    )

    gui_state["controller"] = ConcurrencyController(config=config, event_bus=gui_state["event_bus"])
    gui_state["is_running"] = True
    gui_state["statistics"]["start_time"] = time.time()

    # Start in background thread
    def run_automation():
        logger.info("📍 run_automation() called")
        try:
            logger.info("📦 Importing modules...")
            from bing_rewards.app import execute_searches_for_instance, word_generator
            from bing_rewards.options import get_options
            logger.info("✓ Imports successful")
            
            # Load profiles
            logger.info(f"📂 Loading {len(profiles)} profiles...")
            profile_configs = []
            for profile_name in profiles:
                profile = gui_state["profile_manager"].get_profile(profile_name)
                if not profile:
                    logger.warning(f"  Profile '{profile_name}' not found, creating...")
                    profile = ProfileConfig(profile_name=profile_name)
                    gui_state["profile_manager"].add_profile(profile)
                profile_configs.append(profile)
                logger.info(f"  ✓ Loaded: {profile.profile_name}")

            logger.info(f"✓ Loaded {len(profile_configs)} profiles")

            # Get options
            logger.info("⚙️ Getting options...")
            options = get_options()
            options.desktop_count = desktop_count
            options.mobile_count = mobile_count
            logger.info(f"✓ Options: desktop={desktop_count}, mobile={mobile_count}")

            # Word generator factory
            logger.info("📝 Creating word generator...")
            def words_gen_factory():
                return word_generator()
            logger.info("✓ Word generator ready")

            # Execute searches
            logger.info(" Starting concurrent searches...")
            results = gui_state["controller"].run_concurrent_searches(
                profiles=profile_configs,
                words_gen_factory=words_gen_factory,
                search_executor=lambda inst, wg: execute_searches_for_instance(
                    inst, wg, options, desktop_count, mobile_count
                ),
                options=options,
            )
            logger.info(f"✓ Concurrent searches completed: {len(results)} results")

            # Update statistics
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            total_searches = sum(r.searches_completed for r in results)

            gui_state["statistics"]["successful_instances"] = successful
            gui_state["statistics"]["failed_instances"] = failed
            gui_state["statistics"]["total_searches"] = total_searches

            logger.info(f"✅ Automation completed: {successful} successful, {failed} failed")
            logger.info(f"   - Total searches: {total_searches}")

        except Exception as e:
            logger.error(f"❌ Automation error: {e}", exc_info=True)
            gui_state["event_bus"].emit(
                EventType.INSTANCE_ERROR,
                source="GUI",
                profile_name="SYSTEM",
                data={"error": str(e)},
            )
        finally:
            logger.info("🏁 Cleaning up...")
            gui_state["is_running"] = False
            gui_state["controller"] = None
            logger.info("✓ Cleanup complete")

    thread = threading.Thread(target=run_automation, daemon=True)
    thread.start()
    logger.info(f"🧵 Thread started: {thread.name}")

    return jsonify({"status": "started", "profiles": profiles})
```

**Then:**
1. Restart GUI
2. Click "Start"
3. **Copy ALL terminal output**
4. Look for where it stops

---

## 🎯 Most Likely Causes

### 1. **Import Error**
```python
from bing_rewards.app import execute_searches_for_instance, word_generator
```
**Check:**
```bash
python -c "from bing_rewards.app import execute_searches_for_instance, word_generator; print('✓ OK')"
```

### 2. **Controller Hangs**
The `run_concurrent_searches()` might be hanging or throwing silent errors.

**Check:** Add timeout and logging

### 3. **Thread Not Starting**
The background thread might not be starting.

**Check:** Add logging immediately after `thread.start()`

### 4. **Profile Loading Fails**
Profiles might not be loading correctly.

**Check:** Add logging for each profile load

### 5. **Options Not Configured**
`get_options()` might return None or invalid config.

**Check:** Add logging to show options values

---

## 📊 Information Needed

Please provide:

### 1. **Terminal Output**
```
When you click "Start", what appears in the terminal?
- Any errors?
- Any log messages?
- Does it show "Starting automation..."?
```

### 2. **Browser Console**
```
Press F12 → Console tab
Click "Start"
What errors appear?
```

### 3. **Test Script Results**
```
Run: python test_automation.py (when created)
What happens?
- Browser launches?
- Searches execute?
- Any errors?
```

### 4. **Direct API Test**
```
Run the fetch() command in browser console
What response do you get?
```

---

## 🛠️ Quick Fixes to Try

### Fix 1: Add Timeout
```python
# In gui/app.py start_automation()
def run_automation():
    import time
    start_time = time.time()
    
    
    # Add timeout check
    if time.time() - start_time > 300:  # 5 minutes
        logger.error("⏰ Timeout! Automation took too long")
        break
```

### Fix 2: Simplify to Single Profile
```python
# Test with just 1 profile, 1 search
options.desktop_count = 1
options.mobile_count = 1
```

### Fix 3: Run Synchronously First
```python
# Instead of threading, try running directly
# (Will block GUI but easier to debug)
run_automation()  # Direct call instead of threading
```

---

## ✅ Success Criteria

Automation is working when:

- [ ] Click "Start" → browser launches
- [ ] Searches execute automatically
- [ ] Terminal shows: "Automation completed: X successful"
- [ ] Statistics update (Total Searches counter increases)
- [ ] No "Failed to start" errors in Event Log

---

## 📝 Next Steps

1. **Add detailed logging** to `gui/app.py`
2. **Restart GUI**
3. **Click "Start"** and capture terminal output
4. **Run test scripts** (test_automation.py, test_controller.py)
5. **Report findings** with:
   - Terminal logs
   - Browser console errors
   - Test script output

---

**Priority:** 🔴 **HIGH** - This is blocking the main feature!

**Status:** 🟡 **IN PROGRESS** - Need more data to diagnose

---

*Created: When user reported automation not running*
*Last Updated: Initial debugging plan created*
