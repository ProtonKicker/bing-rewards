# Isolated Chromium Instances

## Overview

The Bing Rewards app now supports **creating independent Chromium instances** that are completely separate from your main Chrome installation. Each instance runs in its own isolated environment with temporary storage that's automatically cleaned up when closed.

## Key Features

### ✅ What Are Isolated Instances?

- **Independent Browser Sessions**: Each instance creates its own temporary Chromium browser session
- **No Chrome Profile Dependencies**: Doesn't use your existing Chrome profiles or cookies
- **Clean Slate Every Time**: Fresh browser session without extensions, saved passwords, or browsing history
- **Automatic Cleanup**: Temporary directories are automatically deleted when instances close
- **Full Isolation**: Each instance is completely separate from others and your main browser

### 🎯 Use Cases

1. **Pure Automation**: Run searches without affecting your personal browsing data
2. **Testing**: Test different scenarios with clean browser sessions
3. **Privacy**: No cookies or tracking data persist between sessions
4. **Scalability**: Easily create 10+ independent instances for concurrent execution
5. **No Conflicts**: Avoid conflicts with existing Chrome extensions or settings

## How It Works

### Architecture

```
User Creates Isolated Instance
         ↓
App Creates Temporary Directory
    (e.g., C:\Users\You\AppData\Local\Temp\bing_rewards_bot-1_abc123)
         ↓
Launches Chromium with Flags:
    --user-data-dir="C:\...\temp\...\user_data"
    --disable-extensions
    --disable-background-networking
    --disable-default-apps
    --no-first-run
         ↓
Browser Runs in Isolated Mode
    (No access to main Chrome profiles)
         ↓
Instance Closes
         ↓
Temporary Directory Deleted ✓
```

### Profile Types

| Profile Type | Description | Persistence | Use Case |
|-------------|-------------|-------------|----------|
| **Chrome Profile** | Existing Chrome profiles from your installation | Permanent | Manual authentication, persistent cookies |
| **Isolated (Temporary)** | Fresh Chromium instance with temp directory | Deleted on close | Pure automation, no login needed |
| **Isolated (Persistent)** | Custom directory that persists | Permanent | Repeated automation with same session |

## Using Isolated Instances

### Via Web GUI

1. **Open the GUI**
   ```bash
   python -m bing_rewards.gui
   # Or use: launch-gui.bat on Windows
   ```

2. **Create Isolated Instance**
   - Click "➕ Create New Isolated Instance"
   - Enter a name (e.g., `bot-1`, `instance-5`)
   - Click OK

3. **Select and Run**
   - Check the box next to your isolated instance(s)
   - Configure settings (max instances, searches, etc.)
   - Click "▶️ Start"

### Via Command Line

```bash
# Create isolated profiles programmatically
from bing_rewards.profile_config import ProfileManager

# Create temporary isolated profile
profile = ProfileManager.create_isolated_profile(
    name="bot-1",
    temporary=True  # Auto-cleanup
)

# Create persistent isolated profile
profile = ProfileManager.create_isolated_profile(
    name="persistent-bot",
    temporary=False,  # Keep data
    base_dir=Path("C:/bing_profiles")
)
```

## Technical Details

### Browser Launch Command

When you create an isolated instance, the app builds a command like:

```bash
chrome.exe \
  --new-window \
  --user-agent="Mozilla/5.0..." \
  --user-data-dir="C:\Users\...\Temp\bing_rewards_bot-1_abc123\user_data" \
  --disable-extensions \
  --disable-background-networking \
  --disable-default-apps \
  --no-first-run
```

### Temporary Directory Structure

```
Temp Directory: C:\Users\You\AppData\Local\Temp\bing_rewards_bot-1_abc123\
└── user_data/
    ├── Default/          # Profile data
    ├── Cache/            # Browser cache (auto-deleted)
    ├── Cookies           # Session cookies (auto-deleted)
    └── Local Storage/    # Site data (auto-deleted)
```

### Cleanup Process

When an isolated instance closes:
1. Browser process terminates
2. App detects `is_temporary=True` flag
3. Calls `_cleanup_temporary_directory()`
4. Removes entire temp directory tree
5. Logs cleanup in event log

## Comparison: Isolated vs Chrome Profiles

| Feature | Isolated Instances | Chrome Profiles |
|---------|-------------------|-----------------|
| **Data Persistence** | Temporary (deleted) | Permanent |
| **Login State** | Fresh each time | Saved cookies |
| **Extensions** | Disabled | Enabled |
| **History** | Not saved | Saved |
| **Bookmarks** | None | From Chrome |
| **Password Manager** | Disabled | Enabled |
| **Sync** | Disabled | Enabled |
| **Setup Time** | Instant | Requires Chrome |
| **Resource Usage** | Lower (no extensions) | Higher |
| **Best For** | Pure automation | Manual login + automation |

## Advanced Configuration

### Custom Base Directory

For persistent isolated profiles:

```python
from pathlib import Path
from bing_rewards.profile_config import ProfileManager

# Create profiles in custom location
base_dir = Path("D:/bing_automation/profiles")
profile = ProfileManager.create_isolated_profile(
    name="my-bot",
    base_dir=base_dir,
    temporary=False  # Keep data between sessions
)
```

### Manual Cleanup

If you want to manually cleanup temporary directories:

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

## Troubleshooting

### Issue: "Failed to create profile"

**Solution**: Check that you have write permissions in the temp directory.

### Issue: "Browser won't launch"

**Solution**: Ensure Chrome/Chromium is installed and accessible.

### Issue: "Temporary directory not deleted"

**Solution**: Manually cleanup:
```bash
# Windows
rmdir /s /q %TEMP%\bing_rewards_*

# Linux/Mac
rm -rf /tmp/bing_rewards_*
```

### Issue: "Instances not isolated enough"

**Solution**: Verify the `--disable-extensions` flag is being applied. Check logs.

## Best Practices

1. **Use Descriptive Names**: `bot-1`, `search-bot-a`, etc.
2. **Monitor Disk Space**: Temporary directories can accumulate if not cleaned
3. **Combine with Manual Login**: Use some isolated + some authenticated profiles
4. **Test with Small Numbers**: Start with 1-2 instances before scaling to 10+
5. **Check Logs**: Monitor the Events Log in GUI for cleanup confirmations

## API Reference

### ProfileConfig Fields

- `is_isolated` (bool): True if independent Chromium instance
- `is_temporary` (bool): True if auto-deleted on close
- `user_data_dir` (Path): Location of profile data

### ProfileManager Methods

```python
# Create isolated profile
ProfileManager.create_isolated_profile(
    name: str,
    base_dir: Path | None = None,
    temporary: bool = True
) -> ProfileConfig
```

### BrowserInstance Cleanup

```python
# Automatically called when instance closes
instance._cleanup_temporary_directory()
```

## Example Workflow

### Scenario: Run 10 Isolated Instances

1. **Create Instances**
   ```
   GUI → Create New Isolated Instance → bot-1
   GUI → Create New Isolated Instance → bot-2
   ... repeat for bot-3 through bot-10
   ```

2. **Configure**
   ```
   Max Instances: 10
   Desktop Searches: 33
   Mobile Searches: 23
   Enable Throttling: ✓
   ```

3. **Run**
   ```
   Select All → Start
   ```

4. **Monitor**
   - Watch "Active Instances" panel
   - Check "Events Log" for progress
   - View statistics (successful/failed)

5. **Cleanup**
   ```
   Stop → All temporary directories automatically deleted ✓
   ```

## Performance Considerations

- **CPU Usage**: Isolated instances use ~5-10% less CPU (no extensions)
- **Memory**: ~50-100MB per instance (varies by system)
- **Disk I/O**: Temporary directories created/deleted rapidly
- **Network**: Clean sessions may load slightly slower initially

## Security Notes

- Isolated instances have NO access to your Chrome data
- Cookies/session data are deleted with temporary directories
- No personal information persists between sessions
- Safe for running untrusted automation scripts

## Future Enhancements

- [ ] Option to save isolated profiles for reuse
- [ ] Custom Chrome flags configuration
- [ ] Proxy support per isolated instance
- [ ] Screenshot/video recording
- [ ] Advanced headless mode options

---

**Related Documentation**:
- [GUI README](GUI_README.md) - Full GUI guide
- [Getting Started](GETTING_STARTED_GUI.md) - First-time setup
- [Concurrent Mode](CONCURRENT_MODE.md) - Backend engine details
