# Bing Rewards Web GUI

## 🎨 Graphical Interface for Multi-Instance Control

A modern, web-based graphical user interface for managing your Bing Rewards concurrent browser automation.

![Status](https://img.shields.io/badge/status-beta-yellow)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## ✨ Features

### Visual Control Panel
- **Real-time monitoring** of all browser instances
- **Live statistics** dashboard (searches, success rate, active instances)
- **Event log** with detailed activity tracking
- **Status indicators** (running/stopped with visual feedback)

### Browser Management
- **Profile selection** - Choose which Chrome profiles to automate
- **Manual authentication** - Launch browsers to sign in manually
- **Instance control** - Start/stop individual browsers
- **Batch operations** - Select all/deselect all profiles

### Configuration
- **Max instances** - Control parallelism (1-20)
- **Search counts** - Set desktop/mobile search targets
- **Eco mode** - Conservative resource usage
- **Throttling** - Enable/disable automatic resource management

### Modern UI
- **Responsive design** - Works on desktop and mobile
- **Beautiful gradients** - Purple theme with smooth animations
- **Dark mode events** - Console-style logging
- **Intuitive layout** - Easy to understand at a glance

---

## 🚀 Quick Start

### 1. Install GUI Dependencies

```bash
cd d:\Github\bing-rewards

# Install Flask and CORS
pip install flask flask-cors

# Or if using uv
uv pip install flask flask-cors
```

### 2. Launch the GUI

```bash
# Method 1: Run as module
python -m bing_rewards.gui

# Method 2: Run the app directly
python bing_rewards/gui/app.py

# Method 3: Use the launcher
python bing_rewards/gui/__main__.py
```

### 3. Open Your Browser

The GUI will automatically open in your default browser at:
```
http://localhost:5000
```

Or manually navigate to that URL.

---

## 📸 Interface Overview

### Header Section
- **Title and branding**
- **Quick description**

### Status Bar
- **Status indicator** (green = running, red = stopped)
- **Control buttons**:
  - 🔄 Refresh Profiles
  - 🔐 Manual Login
  - ▶️ Start Automation
  - ⏹️ Stop Automation

### Statistics Dashboard
Four cards showing:
1. **Total Searches** - Cumulative search count
2. **Active Instances** - Currently running browsers
3. **Successful** - Completed instances
4. **Failed** - Instances with errors

### Profile Selection Panel
- **Checkbox list** of all Chrome profiles
- **Profile name** and **display name**
- **Full path** shown for each profile
- **DEFAULT badge** for default profile
- **Select All / Deselect All** buttons

### Configuration Panel
- **Max Instances** - Number slider (1-20)
- **Desktop Searches** - Target count
- **Mobile Searches** - Target count
- **Eco Mode** - Checkbox for conservative limits
- **Enable Throttling** - Checkbox for resource management

### Active Instances Panel
- **Real-time list** of running browser instances
- **Instance ID** and **profile name**
- **State badge** (Running, Searching, Completed, Error)
- **Statistics per instance**:
  - Searches completed
  - Process ID (PID)
  - Current status

### Events Log
- **Chronological feed** of all system events
- **Color-coded** by type:
  - 🔵 INFO - Blue
  - 🟢 SUCCESS - Green
  - 🔴 ERROR - Red
- **Timestamp** for each event
- **Event data** details

---

## 🎯 How to Use

### Step 1: Select Profiles
1. Click **🔄 Refresh Profiles** to load available Chrome profiles
2. Check the boxes next to profiles you want to automate
3. Use **Select All** or **Deselect All** for quick selection

### Step 2: Configure Settings
1. Set **Max Instances** (recommended: start with 3-5)
2. Adjust **Desktop/Mobile Searches** if needed
3. Enable **Eco Mode** for low-end systems
4. Keep **Throttling** enabled for automatic resource management

### Step 3: Manual Authentication (First Time Only)
1. Select the profiles you want to authenticate
2. Click **🔐 Manual Login**
3. Sign in to your Microsoft account in each browser window
4. Close the browsers manually after signing in
5. Return to the GUI

### Step 4: Start Automation
1. Verify profiles are selected
2. Review configuration
3. Click **▶️ Start**
4. Watch the magic happen!

### Step 5: Monitor Progress
- **Statistics update** every 2 seconds
- **Instance list** shows real-time status
- **Event log** displays activity as it happens

### Step 6: Stop When Done
- Click **⏹️ Stop** to gracefully shutdown all instances
- System will complete current searches and close browsers

---

## 🎨 UI Design Features

### Color Scheme
- **Primary**: Purple gradient (#667eea to #764ba2)
- **Success**: Green (#22c55e)
- **Error**: Red (#ef4444)
- **Info**: Blue (#60a5fa)
- **Background**: White panels with subtle shadows

### Responsive Layout
- **Grid system** adapts to screen size
- **Mobile-friendly** on smaller screens
- **Scrollable panels** for long lists
- **Fixed header** for easy navigation

### Visual Feedback
- **Hover effects** on interactive elements
- **Smooth transitions** (0.2s ease)
- **Glowing status dots** when running
- **Color-coded badges** for quick recognition

---

## 🔧 API Reference

The GUI exposes a REST API at `http://localhost:5000/api`

### Endpoints

#### `GET /api/status`
Get current system status
```json
{
  "is_running": false,
  "instances": [...],
  "statistics": {...}
}
```

#### `GET /api/profiles`
List available Chrome profiles
```json
[
  {
    "name": "Default",
    "display_name": "Default",
    "path": "C:\\...\\Default",
    "is_default": true,
    "is_saved": false
  }
]
```

#### `GET /api/config`
Get current configuration

#### `POST /api/config`
Update configuration
```json
{
  "max_instances": 10,
  "eco_mode": false,
  "throttling": true
}
```

#### `POST /api/start`
Start automation
```json
{
  "profiles": ["Default", "Profile 1"],
  "max_instances": 10,
  "eco_mode": false
}
```

#### `POST /api/stop`
Stop automation

#### `POST /api/manual-login`
Launch browsers for manual authentication
```json
{
  "profiles": ["Default", "Profile 1"]
}
```

#### `GET /api/events`
Get recent events (last 50)

#### `GET /api/instances/<id>`
Get specific instance details

#### `POST /api/instances/<id>/close`
Close a specific instance

---

## 🛠️ Development

### File Structure
```
bing_rewards/gui/
├── app.py                 # Flask server and API
├── __main__.py           # Launcher script
├── requirements.txt      # Python dependencies
└── templates/
    └── gui.html         # Main HTML/CSS/JS interface
```

### Running in Development Mode

```bash
# Enable Flask debug mode
export FLASK_ENV=development
python -m bing_rewards.gui
```

### Customizing the UI

Edit `bing_rewards/gui/templates/gui.html`:
- **CSS styles** - Modify the `<style>` section
- **Layout** - Change HTML structure
- **JavaScript** - Update API calls or add features

---

## 📊 Statistics Explained

### Total Searches
Sum of all searches completed across all instances. Updates in real-time.

### Active Instances
Number of browser instances currently running. Decreases as instances complete.

### Successful Instances
Count of instances that completed without errors.

### Failed Instances
Count of instances that encountered errors. Check the event log for details.

---

## 🎯 Tips for Best Experience

### Performance
1. **Start small** - Begin with 3-5 instances
2. **Monitor resources** - Watch CPU/memory in your system tray
3. **Use eco mode** - On laptops or older systems
4. **Close other apps** - Free up resources for automation

### Workflow
1. **Authenticate first** - Use manual login before automating
2. **Test with dry run** - Try with 1-2 instances first
3. **Save profile groups** - Remember which profiles work best
4. **Check event log** - Debug issues quickly

### Browser Management
1. **Name your profiles** - Use descriptive names in Chrome
2. **Keep profiles clean** - Remove unused extensions
3. **Update Chrome** - Ensure latest version for compatibility
4. **Close Chrome** - Before starting automation

---

## 🐛 Troubleshooting

### GUI Won't Load
**Problem**: Browser shows error or won't connect

**Solution**:
```bash
# Check if Flask is running
# Look for: "Running on http://0.0.0.0:5000"

# Restart the GUI
python -m bing_rewards.gui
```

### Profiles Not Showing
**Problem**: Profile list is empty

**Solution**:
1. Click **🔄 Refresh Profiles**
2. Make sure Chrome is installed
3. Verify Chrome profiles exist:
   - Windows: `%LOCALAPPDATA%\Google\Chrome\User Data`
   - Linux: `~/.config/google-chrome`

### Start Button Disabled
**Problem**: Can't click Start

**Solution**:
- Select at least one profile checkbox
- Wait for any running automation to finish

### Instances Not Starting
**Problem**: Click Start but nothing happens

**Solution**:
1. Check event log for error messages
2. Verify profiles are authenticated
3. Try manual login for selected profiles
4. Reduce max instances if system is overloaded

### High CPU Usage
**Problem**: System becomes slow during automation

**Solution**:
1. Enable **Eco Mode**
2. Reduce **Max Instances** to 3-5
3. Enable **Throttling**
4. Close other resource-intensive applications

---

## 🚀 Future Enhancements

Planned features:
- [ ] Profile group presets (save/load configurations)
- [ ] Scheduling (run at specific times)
- [ ] Search progress visualization (charts/graphs)
- [ ] Export statistics (CSV/JSON)
- [ ] Dark/light theme toggle
- [ ] Custom CSS themes
- [ ] WebSocket for real-time updates
- [ ] Mobile app (React Native)
- [ ] System tray integration
- [ ] Notifications (desktop/mobile)

---

## 📝 License

MIT License - Same as main Bing Rewards project

---

## 🙋 Need Help?

### Documentation
- **Main README**: `README.md`
- **Concurrent Mode Guide**: `CONCURRENT_MODE.md`
- **Quick Start**: `QUICKSTART_CONCURRENT.md`

### Support
1. Check the **Events Log** for error messages
2. Review **CONCURRENT_MODE.md** for troubleshooting
3. Run tests: `python test_concurrent.py`
4. Open an issue on GitHub

---

## 🎉 Enjoy Your New GUI!

You now have full visual control over your Bing Rewards automation. Sit back, watch the searches roll in, and earn rewards faster than ever!

**Happy Searching!** 🔍✨
