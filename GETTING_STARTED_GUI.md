#  Getting Started with Bing Rewards GUI

## Your Complete Visual Control Panel

Welcome to the **Bing Rewards Web GUI** - your graphical command center for multi-instance browser automation!

---

## ⚡ 3-Minute Setup

### Step 1: Install GUI (One Time Only)

**Option A: Use the Batch File (Easiest)**
```bash
# Double-click this file:
launch-gui.bat

# Or run from command line:
.\launch-gui.bat
```

**Option B: Manual Installation**
```bash
# Navigate to project folder
cd d:\Github\bing-rewards

# Install Flask (web framework)
pip install flask flask-cors
```

### Step 2: Launch the GUI

**Method 1: Double-click**
```
launch-gui.bat
```

**Method 2: Command line**
```bash
python -m bing_rewards.gui
```

**Method 3: Direct execution**
```bash
python bing_rewards/gui/app.py
```

### Step 3: Access the Interface

The GUI will **automatically open** in your browser at:
```
http://localhost:5000
```

If it doesn't open automatically, manually navigate to that URL.

---

## 🎯 First Use Walkthrough

### 1. You'll See the Main Dashboard

The interface has:
- **Purple gradient header** with title
- **Status bar** with control buttons
- **Statistics cards** showing metrics
- **Profile selection panel** on the left
- **Configuration panel** on the right
- **Active instances** view below
- **Event log** for monitoring

### 2. Select Your Chrome Profiles

1. Click **🔄 Refresh Profiles** button
2. You'll see all your Chrome profiles listed
3. **Check the boxes** next to profiles you want to use
4. The **Default** profile is usually already authenticated

**Tip**: Profiles are named like:
- `Default` - Your main Chrome profile
- `Profile 1`, `Profile 2`, etc. - Additional profiles

### 3. Configure Settings

In the **Configuration** panel:

| Setting | Recommended Value | Description |
|---------|------------------|-------------|
| **Max Instances** | 5 (start small) | How many browsers run at once |
| **Desktop Searches** | 33 | Target searches per desktop profile |
| **Mobile Searches** | 23 | Target searches per mobile profile |
| **Eco Mode** | ☐ Unchecked | Check for low-end systems |
| **Enable Throttling** | ☑ Checked | Uncheck for maximum speed |

**Beginner Tip**: Start with **3-5 instances max** to test your system.

### 4. Manual Authentication (First Time Only)

If you've never signed in to Bing with your Chrome profiles:

1. **Select the profiles** you want to authenticate
2. Click **🔐 Manual Login** button
3. **Chrome windows will open** automatically
4. In each window:
   - Go to https://bing.com
   - Click **Sign In** (top right)
   - Enter your Microsoft account credentials
   - Complete any CAPTCHA if shown
   - **Keep the window open**
5. After signing in to **all** profiles, **close the browsers manually**
6. Return to the GUI

**Important**: You need to do this **only once** per profile. The GUI remembers authenticated profiles.

### 5. Start Automation!

1. ✅ Verify profiles are selected (checkboxes checked)
2. ✅ Review configuration settings
3. ✅ Click the big **▶️ Start** button

**What happens next:**
- Status indicator turns **green** (running)
- **Active Instances** panel populates
- You'll see browsers launching
- **Statistics update** in real-time
- **Event log** shows progress

### 6. Monitor Progress

Watch the dashboard:

**Statistics Cards** (top):
- **Total Searches** - Increases as searches complete
- **Active Instances** - Shows running browsers
- **Successful** - Completed without errors
- **Failed** - Had problems (check event log)

**Active Instances Panel**:
- Each running browser shown as a card
- **State badge** shows: Running → Searching → Completed
- **Search count** updates live
- **PID** shows process ID

**Events Log**:
- Scrolling feed of all activity
- **Blue** = Info (instance launched)
- **Green** = Success (search completed)
- **Red** = Error (something went wrong)

### 7. Stop When Done

Two ways to stop:

**Graceful Stop** (recommended):
- Click **⏹️ Stop** button
- System finishes current searches
- Browsers close automatically
- Status turns **red** (stopped)

**Emergency Stop**:
- Press **Ctrl+C** in the terminal running the GUI
- Immediate shutdown
- Use only if something goes wrong

---

## 📊 Understanding the Dashboard

### Status Bar (Top)

```
● Running    [🔄 Refresh] [🔐 Manual Login] [▶️ Start] [⏹️ Stop]
```

- **Green dot** = Automation is running
- **Red dot** = Stopped
- **Buttons** control the automation

### Statistics Cards

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   0          │ │   0          │ │   0          │ │   0          │
│Total Searches│ │Active Inst.  │ │Successful    │ │Failed        │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

Real-time metrics updated every 2 seconds.

### Profile Selection Panel

```
📁 Select Profiles
┌────────────────────────────────────┐
│ ☐ Default [DEFAULT]                │
│    C:\Users\You\...\Default        │
│                                    │
│ ☐ Profile 1                        │
│    C:\Users\You\...\Profile 1      │
└────────────────────────────────────┘
[Select All] [Deselect All]
```

Check boxes to choose which profiles to automate.

### Configuration Panel

```
⚙️ Configuration
Max Instances:      [10    ]
Desktop Searches:   [33    ]
Mobile Searches:    [23    ]
☐ Eco Mode
☑ Enable Throttling
```

Adjust settings before starting.

### Active Instances Panel

```
🖥️ Active Instances
┌────────────────────────────────────┐
│ instance_0_Default        [RUNNING]│
│ Profile: Default                   │
│ ┌────────────────┬────────┐       │
│ │Searches│  PID   │ Status │       │
│ │   15   │ 12345  │Running │       │
│ └────────┴────────┴────────┘       │
└────────────────────────────────────┘
```

Shows each running browser with live stats.

### Events Log

```
📊 Events Log
┌────────────────────────────────────┐
│ 12:34:56 [SUCCESS] Automation      │
│              started               │
│                                    │
│ 12:34:57 [INFO] instance_0_        │
│              Default launched      │
│                                    │
│ 12:34:58 [INFO] Default Search     │
│              5/33                  │
└────────────────────────────────────┘
```

Chronological activity feed.

---

## 🎨 Visual Indicators

### Color Coding

| Color | Meaning | Where Used |
|-------|---------|------------|
| 🟢 **Green** | Running/Success | Status dot, success events |
| 🔴 **Red** | Stopped/Error | Status dot, error events |
| 🔵 **Blue** | Info | Info events, primary buttons |
| 🟣 **Purple** | Branding | Background gradient |
| ⚪ **White** | Panels | Card backgrounds |

### State Badges

In the Active Instances panel, you'll see colored badges:

- **RUNNING** (green) - Browser launched and ready
- **SEARCHING** (blue) - Currently performing searches
- **COMPLETED** (purple) - Finished all searches
- **ERROR** (red) - Something went wrong

---

## 🔧 Common Tasks

### Task 1: Add a New Profile

1. Create the profile in Chrome:
   - Open Chrome
   - Click profile icon (top right)
   - Click **Add**
   - Sign in to Microsoft account in new profile
   - Close Chrome

2. In GUI:
   - Click **🔄 Refresh Profiles**
   - Your new profile appears in the list
   - Check its checkbox
   - Ready to use!

### Task 2: Change Settings Mid-Run

**Important**: Settings are applied when you click **Start**.

To change settings:
1. Click **⏹️ Stop** to halt current run
2. Adjust configuration sliders/checkboxes
3. Click **▶️ Start** again with new settings

### Task 3: Check Authentication Status

The GUI doesn't show auth status directly yet, but you can:

**Method 1: Test with Manual Login**
1. Select a profile
2. Click **🔐 Manual Login**
3. If Bing shows "Signed in as...", it's authenticated
4. Close the browser

**Method 2: Run a Test**
1. Select just one profile
2. Set Max Instances = 1
3. Click **▶️ Start**
4. Watch event log for errors
5. If searches complete, it's authenticated

### Task 4: Run Multiple Batches

Want to run different profile groups:

**Batch 1**:
1. Select profiles: Default, Profile 1, Profile 2
2. Click **▶️ Start**
3. Wait for completion
4. Click **⏹️ Stop**

**Batch 2**:
1. Deselect all (or select different profiles)
2. Adjust settings if needed
3. Click **▶️ Start**
4. Monitor progress

---

## 🐛 Quick Troubleshooting

### Problem: "No profiles found"

**Solution**:
1. Make sure Chrome is installed
2. Click **🔄 Refresh Profiles**
3. If still empty, create a Chrome profile:
   - Open Chrome
   - Click profile icon
   - Add a profile
   - Close Chrome
   - Refresh in GUI

### Problem: "Already running" error

**Solution**:
- Check if status dot is green
- Look at Active Instances panel
- If running, click **⏹️ Stop** first
- Wait for instances to close
- Then click **▶️ Start** again

### Problem: Browsers won't launch

**Solution**:
1. Check event log for error message
2. Verify Chrome is installed at standard location
3. Try manual login first: **🔐 Manual Login**
4. Check Windows Task Manager for stuck Chrome processes

### Problem: High CPU usage

**Solution**:
1. Click **⏹️ Stop**
2. Enable **Eco Mode** checkbox
3. Reduce **Max Instances** to 3-5
4. Ensure **Enable Throttling** is checked
5. Click **▶️ Start** again

### Problem: Searches not counting

**Solution**:
- Verify you're signed in to Microsoft account
- Check that cookies are enabled
- Try manual authentication for the profile
- Increase **search delay** in config file

---

## 📈 Pro Tips

### Optimize Performance

1. **Start Conservative**
   - First run: 2-3 instances
   - Second run: 5 instances
   - Find your system's sweet spot

2. **Monitor Resources**
   - Open Task Manager (Ctrl+Shift+Esc)
   - Watch CPU and Memory tabs
   - Adjust Max Instances accordingly

3. **Use Profile Groups**
   - Morning batch: Profiles 1-5
   - Evening batch: Profiles 6-10
   - Avoid running all at once if system struggles

### Maximize Rewards

1. **Daily Routine**
   - Run once in morning
   - Run once in evening
   - Consistency beats marathon sessions

2. **Profile Rotation**
   - Don't use same profiles every day
   - Rotate between groups
   - Looks more natural to Bing

3. **Timing**
   - Spread searches throughout day
   - Don't run all at same time
   - Use GUI's batch capability

### GUI Best Practices

1. **Keep Tab Open**
   - Monitor progress visually
   - Catch errors early
   - See real-time statistics

2. **Use Event Log**
   - First place to check for issues
   - Shows exact error messages
   - Helps debug problems

3. **Save Configurations**
   - Take screenshot of good settings
   - Note what works for your system
   - Reference for future runs

---

## 🎓 Next Steps

### Beginner → Intermediate

Once comfortable with basics:

1. **Read Full Documentation**
   - `GUI_README.md` - Complete feature list
   - `CONCURRENT_MODE.md` - Technical details

2. **Experiment with Settings**
   - Try different instance counts
   - Test eco mode impact
   - Find optimal configuration

3. **Join the Community**
   - Check GitHub issues
   - Share your configurations
   - Learn from others

### Intermediate → Advanced

Ready for power features:

1. **Edit Config File**
   - Location: `%APPDATA%\bing-rewards\config.json`
   - Fine-tune thresholds
   - Customize behavior

2. **Use CLI Alongside GUI**
   - Run CLI for quick tests
   - Use GUI for monitoring
   - Best of both worlds

3. **Contribute**
   - Report bugs on GitHub
   - Suggest new features
   - Help improve the GUI

---

## 📞 Getting Help

### Documentation Hierarchy

1. **This Guide** (`GETTING_STARTED_GUI.md`) - First place to look
2. **GUI_README.md** - Complete GUI reference
3. **CONCURRENT_MODE.md** - Technical backend details
4. **QUICKSTART_CONCURRENT.md** - CLI quick start
5. **GitHub Issues** - Community problems/solutions

### Support Checklist

Before asking for help:

- [ ] Checked event log for error messages
- [ ] Verified Chrome is installed
- [ ] Confirmed profiles are authenticated
- [ ] Tried with fewer instances (2-3)
- [ ] Reviewed troubleshooting section
- [ ] Checked GitHub issues

### Where to Ask

1. **GitHub Issues**: https://github.com/jack-mil/bing-rewards/issues
2. **Discussions**: GitHub Discussions tab
3. **Community**: Reddit, Discord (if available)

---

## 🎉 You're Ready!

Congratulations! You now have:

✅ A beautiful, modern web GUI  
✅ Full visual control over automation  
✅ Real-time monitoring and statistics  
✅ Easy profile management  
✅ Batch operation capabilities  

**Start earning Bing Rewards faster than ever!**

### Your First Run Checklist

- [ ] GUI installed and launched
- [ ] Browser opened to http://localhost:5000
- [ ] Profiles selected
- [ ] Settings configured
- [ ] Manual authentication completed (if needed)
- [ ] Clicked **▶️ Start**
- [ ] Watching progress in real-time

**Happy automating!** 🚀✨

---

*Last Updated: 2026-03-26*  
*GUI Version: 1.0.0 (Beta)*
