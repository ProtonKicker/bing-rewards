# Quick Start: Isolated Instances

## 3-Minute Guide to Creating Independent Chromium Instances

This guide shows you how to create and run **isolated Chromium instances** - independent browser sessions that don't use your Chrome profiles and are automatically cleaned up.

---

## What Are Isolated Instances?

**Isolated instances** are temporary, independent Chromium browser sessions:
- ✅ **No Chrome Profile Needed**: Creates its own temporary browser data
- ✅ **Clean Session**: No extensions, no saved cookies, no history
- ✅ **Auto-Cleanup**: Deleted automatically when closed
- ✅ **Privacy**: No persistent data left behind
- ✅ **Scalable**: Easy to run 10+ instances concurrently

**Best for**: Pure automation without affecting your personal Chrome browser.

---

## Method 1: Web GUI (Easiest)

### Step 1: Launch GUI

```bash
python -m bing_rewards.gui
```

Or on Windows, double-click:
```
launch-gui.bat
```

### Step 2: Create Isolated Instance

1. Wait for GUI to open at `http://localhost:5000`
2. Click **"➕ Create New Isolated Instance"** button
3. Enter a name: `bot-1`, `bot-2`, etc.
4. Click **OK**

You'll see the new profile appear with:
- ✅ Green **"ISOLATED"** badge
- ⚠️ Orange **"Temporary (auto-cleanup)"** warning

### Step 3: Run Automation

1. **Check the box** next to your isolated instance(s)
2. **Configure settings**:
   - Max Instances: `10` (or however many you created)
   - Desktop Searches: `33`
   - Mobile Searches: `23`
   - Enable Throttling: ✓
3. Click **"▶️ Start"**

### Step 4: Watch It Run

- Browser windows will open (one per instance)
- Each will execute searches automatically
- Watch progress in **"Active Instances"** panel
- View real-time updates in **"Events Log"**

### Step 5: Stop & Cleanup

1. Click **"⏹️ Stop"** when done
2. All temporary directories are **automatically deleted** ✓
3. No manual cleanup needed!

---

## Method 2: Command Line (Advanced)

### Create Isolated Profiles

```python
from bing_rewards.profile_config import ProfileManager

# Create 10 isolated profiles
profiles = []
for i in range(10):
    profile = ProfileManager.create_isolated_profile(
        name=f"bot-{i+1}",
        temporary=True  # Auto-cleanup
    )
    profiles.append(profile)
    print(f"Created: {profile.profile_name}")
    print(f"  Location: {profile.user_data_dir}")
    print(f"  Isolated: {profile.is_isolated}")
    print(f"  Temporary: {profile.is_temporary}")
```

### Run Concurrent Automation

```python
from bing_rewards.app import run_concurrent_mode
from bing_rewards.options import get_options

# Get options
options = get_options()

# Set concurrent mode
options.concurrent = True
options.max_instances = 10

# Run with isolated profiles
run_concurrent_mode(options)
```

---

## Complete Example: From Scratch to Running

### Full Script

```python
#!/usr/bin/env python3
"""
Create and run 10 isolated instances for Bing Rewards.
"""

from bing_rewards.profile_config import ProfileManager
from bing_rewards.app import run_concurrent_mode
from bing_rewards.options import get_options

def main():
    print("Creating 10 isolated browser instances...")
    
    # Create isolated profiles
    profiles = []
    for i in range(10):
        profile = ProfileManager.create_isolated_profile(
            name=f"bot-{i+1}",
            temporary=True
        )
        profiles.append(profile)
        print(f"  ✓ Created {profile.profile_name}")
    
    print(f"\nCreated {len(profiles)} isolated profiles")
    print("Starting concurrent automation...\n")
    
    # Configure and run
    options = get_options()
    options.concurrent = True
    options.max_instances = 10
    options.desktop = 33
    options.mobile = 23
    
    # Run automation
    run_concurrent_mode(options)
    
    print("\n✓ Automation complete!")
    print("✓ All temporary directories cleaned up automatically")

if __name__ == "__main__":
    main()
```

**Run it:**
```bash
python run_isolated_bot.py
```

---

## Understanding the Output

### When Creating Profile

```
Created isolated profile: bot-1 at C:\Users\You\AppData\Local\Temp\bing_rewards_bot-1_abc123\user_data
```

**What this means:**
- Profile named `bot-1` created
- Temporary directory at: `C:\Users\You\AppData\Local\Temp\bing_rewards_bot-1_abc123\`
- Browser data will be stored in: `...\user_data\` subdirectory

### When Running

```
[bot-1] Launching browser for profile bot-1
[bot-1] Browser launched [PID: 12345]
[bot-1] Search 1/33: random query
[bot-1] Search 2/33: another query
...
```

**What this means:**
- Each instance logs its progress
- PID shows the browser process ID
- Searches are being executed automatically

### When Cleaning Up

```
[bot-1] Closing browser [12345]
[bot-1] Browser [12345] closed successfully
[bot-1] Cleaning up temporary directory: C:\Users\...\bing_rewards_bot-1_abc123\
```

**What this means:**
- Browser process terminated
- Temporary directory being deleted
- No data persists ✓

---

## Comparing Profile Types

### Isolated Profile (New)

```python
profile = ProfileManager.create_isolated_profile("bot-1", temporary=True)
```

**Characteristics:**
- ✅ Creates new temporary directory
- ✅ No Chrome profile needed
- ✅ Auto-deleted on close
- ✅ No extensions
- ✅ Clean cookies/cache
- ✅ Best for pure automation

### Chrome Profile (Traditional)

```python
profile = ProfileConfig(profile_name="Default")
```

**Characteristics:**
- ✅ Uses existing Chrome profile
- ✅ Saved cookies/login state
- ✅ Extensions enabled
- ✅ Persistent data
- ✅ Best for authenticated automation

### Mixed Usage

```python
# Create 5 isolated instances
isolated = [
    ProfileManager.create_isolated_profile(f"bot-{i}")
    for i in range(5)
]

# Add 5 Chrome profiles
chrome = [
    ProfileConfig(profile_name=f"Profile {i}")
    for i in range(5)
]

# Combine and run together
all_profiles = isolated + chrome
```

**Result**: 10 instances running together - 5 isolated + 5 authenticated!

---

## Troubleshooting

### "Failed to create profile"

**Check**: Temp directory exists and is writable

```bash
# Windows
dir %TEMP%

# Linux/Mac
ls -ld /tmp
```

**Fix**: Ensure you have write permissions

### "Browser won't launch"

**Check**: Chrome/Chromium is installed

```bash
# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" --version

# Linux
google-chrome --version

# Mac
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version
```

**Fix**: Install Chrome or update path in config

### "Temp directories not deleted"

**Manual cleanup:**

```bash
# Windows
rmdir /s /q %TEMP%\bing_rewards_*

# Linux/Mac
rm -rf /tmp/bing_rewards_*
```

---

## Performance Tips

### Optimal Instance Count

| System RAM | Recommended Instances |
|------------|----------------------|
| 4GB | 5-8 instances |
| 8GB | 10-15 instances |
| 16GB | 15-20 instances |
| 32GB+ | 20+ instances |

### Resource Usage

**Per isolated instance:**
- CPU: ~5-8% (lower than Chrome profiles)
- Memory: ~80MB (no extensions)
- Disk I/O: Minimal (temp writes only)

**Tips:**
- Enable throttling to prevent overload
- Use eco mode on battery power
- Monitor CPU/RAM in Task Manager
- Start with fewer instances, scale up gradually

---

## Advanced Features

### Persistent Isolated Profiles

Want to keep the browser data between sessions:

```python
profile = ProfileManager.create_isolated_profile(
    name="persistent-bot",
    temporary=False  # Don't auto-delete
)
```

**Use case**: Reuse same session multiple times with accumulated cookies.

### Custom Base Directory

Store isolated profiles in specific location:

```python
from pathlib import Path

profile = ProfileManager.create_isolated_profile(
    name="my-bot",
    base_dir=Path("D:/bing_profiles"),
    temporary=False
)
```

**Result**: Profile data stored at `D:/bing_profiles/my-bot/`

### Manual Cleanup

```python
import shutil
from bing_rewards.profile_config import ProfileManager

manager = ProfileManager()
for profile in manager.get_active_profiles():
    if profile.is_temporary and profile.user_data_dir:
        temp_dir = profile.user_data_dir.parent
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            print(f"Cleaned up: {temp_dir}")
```

---

## Best Practices

### ✅ Do

- Use descriptive names: `bot-1`, `search-bot-a`, etc.
- Start with 1-2 instances to test
- Enable throttling for stability
- Monitor resource usage
- Let auto-cleanup do its job

### ❌ Don't

- Run 10+ instances immediately (test with fewer first)
- Disable throttling unless necessary
- Mix too many different profile types (can be confusing)
- Ignore CPU/memory warnings

---

## Next Steps

### Learn More

- **[Complete Guide](ISOLATED_INSTANCES.md)** - Full feature documentation
- **[Architecture](ARCHITECTURE_ISOLATED_INSTANCES.md)** - How it works internally
- **[GUI Guide](GETTING_STARTED_GUI.md)** - Web interface walkthrough

### Try These

1. **Create 10 isolated instances** via GUI
2. **Run concurrent searches** with all 10
3. **Watch the cleanup** happen automatically
4. **Compare performance** vs Chrome profiles

### Experiment

- Mix isolated + Chrome profiles
- Try persistent isolated profiles
- Test different instance counts
- Monitor resource usage

---

## Summary

**Isolated instances** give you:
- ✅ Independent Chromium sessions
- ✅ No Chrome profile dependencies
- ✅ Automatic cleanup
- ✅ Better performance (no extensions)
- ✅ Enhanced privacy (no persistent data)

**Get started in 3 steps:**
1. Launch GUI: `python -m bing_rewards.gui`
2. Create isolated instance: Click "➕ Create New Isolated Instance"
3. Run automation: Select instance → Click "▶️ Start"

**That's it!** The app handles everything else automatically. 

---

**Questions?** Check the [full documentation](ISOLATED_INSTANCES.md) or run `bing-rewards --help`
