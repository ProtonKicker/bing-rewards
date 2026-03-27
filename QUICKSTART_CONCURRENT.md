# Quick Start - Bing Rewards Concurrent Mode

## 🚀 Get Started in 3 Minutes

### Step 1: Install Dependencies

```bash
# Navigate to the project directory
cd d:\Github\bing-rewards

# Install with new dependencies
pip install -e .
# or if using uv
uv pip install -e .
```

### Step 2: Verify Installation

```bash
# Check that bing-rewards is available
bing-rewards --version

# Verify concurrent mode options are available
bing-rewards --help | findstr "concurrent"
```

You should see:
```
-C, --concurrent      Enable concurrent multi-instance mode
--max-instances       Maximum number of parallel browser instances
--list-profiles       List available Chrome profiles
--manual-login        Launch browsers for manual authentication
```

### Step 3: Check Available Profiles

```bash
bing-rewards --list-profiles
```

Example output:
```
=== Available Chrome Profiles ===
1. Default [DEFAULT]
   Path: C:\Users\YourName\AppData\Local\Google\Chrome\User Data\Default

2. Profile 1
   Path: C:\Users\YourName\AppData\Local\Google\Chrome\User Data\Profile 1
```

---

## ⚡ Basic Usage

### Run Concurrent Mode (Default Settings)

This will run up to 10 browser instances simultaneously:

```bash
bing-rewards --concurrent
```

### Run with Custom Instance Count

```bash
bing-rewards --concurrent --max-instances 5
```

### Run with Specific Profiles

```bash
bing-rewards --concurrent --profile "Default" "Profile 1"
```

### Test Without Actually Searching (Dry Run)

```bash
bing-rewards --concurrent --dryrun --max-instances 3
```

---

## 🔐 First-Time Setup: Manual Authentication

If you haven't signed in to your Microsoft accounts in Chrome yet:

### 1. Launch Browsers for Manual Login

```bash
bing-rewards --manual-login --profile "Default" "Profile 1" "Profile 2"
```

This opens Chrome windows without automation.

### 2. Sign In to Each Account

- Go to https://bing.com in each browser
- Sign in with your Microsoft account
- Complete any CAPTCHA if prompted
- **Keep browsers open** while signing in

### 3. Close Browsers Manually

After signing in to all accounts, close the browser windows.

### 4. Run Automated Searches

```bash
bing-rewards --concurrent --profile "Default" "Profile 1" "Profile 2"
```

The script will now use your authenticated sessions!

---

## 🎛️ Common Scenarios

### Scenario 1: Conservative Resource Usage (Low-End PC)

```bash
bing-rewards --concurrent --eco-mode --max-instances 3
```

### Scenario 2: Maximum Speed (High-End PC)

```bash
bing-rewards --concurrent --no-throttle --max-instances 15
```

### Scenario 3: Quick Test Run

```bash
bing-rewards --concurrent --dryrun --max-instances 2 --count 3
```

Does only 3 searches per instance for testing.

### Scenario 4: Desktop Searches Only

```bash
bing-rewards --concurrent --desktop --max-instances 5
```

### Scenario 5: Mobile Searches Only

```bash
bing-rewards --concurrent --mobile --max-instances 5
```

---

## 📊 Monitor Progress

While running, you'll see output like:

```
=== Starting Concurrent Multi-Instance Mode ===
Max Instances: 5
Throttling: Enabled
Eco Mode: Disabled

Running 5 profile(s): ['Default', 'Profile 1', 'Profile 2', 'Profile 3', 'Profile 4']

[instance_0_Default] Doing 33 desktop searches
[instance_1_Profile 1] Doing 33 desktop searches
...

  [Default] Search 5/33
  [Profile 1] Search 4/33
...

=== Execution Summary ===
Total Instances: 5
Successful: 5
Failed: 0
Total Searches: 165
Success Rate: 100.0%
Average Duration: 245.3s
========================
```

---

## ⚙️ Configuration File

For advanced settings, edit:

**Windows:** `%APPDATA%\bing-rewards\config.json`  
**Linux/Mac:** `~/.config/bing-rewards/config.json`

Example configuration:

```json
{
  "concurrency": {
    "max_instances": 10,
    "enable_throttling": true,
    "cpu_threshold": 80.0,
    "memory_threshold": 85.0,
    "eco_mode": false,
    "instance_timeout": 600
  },
  "desktop_count": 33,
  "mobile_count": 23,
  "search_delay": 6.0
}
```

---

## 🛑 Stopping Execution

### Graceful Stop
Press `CTRL+C` once - the system will request shutdown and finish current searches.

### Force Stop
Press `CTRL+C` twice within 2 seconds - immediate termination.

---

## ❓ Troubleshooting

### "No profiles found"

**Solution:** Create Chrome profiles or specify explicitly:
```bash
bing-rewards --concurrent --profile "Default"
```

### "Chrome not found"

**Solution:** Install Chrome or specify full path:
```bash
bing-rewards --concurrent --exe "C:\Program Files\Google\Chrome\Application\chrome.exe"
```

### High CPU Usage

**Solution:** Reduce instances or enable eco mode:
```bash
bing-rewards --concurrent --eco-mode --max-instances 3
```

### Authentication Errors

**Solution:** Re-run manual login:
```bash
bing-rewards --manual-login --profile "Profile 1"
```

---

## 📈 Performance Tips

1. **Start Small**: Begin with 3-5 instances
2. **Monitor First Run**: Watch CPU/memory usage
3. **Use SSD**: Faster profile loading
4. **Close Other Apps**: Free up resources
5. **Enable Eco Mode**: On laptops or low-end systems

---

## 🎯 Next Steps

After getting comfortable with basic concurrent mode:

1. **Explore Advanced Options**: See `bing-rewards --help`
2. **Read Full Documentation**: `CONCURRENT_MODE.md`
3. **Run Tests**: `python test_concurrent.py`
4. **Customize Config**: Edit config file for your hardware
5. **Monitor Resources**: Use Task Manager or system monitor

---

## 📚 Additional Resources

- **Full Documentation**: `CONCURRENT_MODE.md`
- **Implementation Details**: `IMPLEMENTATION_SUMMARY.md`
- **Test Suite**: `test_concurrent.py`
- **Original README**: `README.md`

---

## ✅ Success Checklist

Before you're done, verify:

- [ ] Dependencies installed (`pip install -e .`)
- [ ] Chrome profiles identified (`bing-rewards --list-profiles`)
- [ ] Manual authentication completed (if needed)
- [ ] Test run successful (`bing-rewards --concurrent --dryrun`)
- [ ] Resource limits appropriate for your system
- [ ] Understand how to stop execution (CTRL+C)

**You're ready to start earning rewards faster with concurrent mode!** 🎉

---

**Need Help?**  
Check `CONCURRENT_MODE.md` for detailed troubleshooting or run:
```bash
bing-rewards --help
```
