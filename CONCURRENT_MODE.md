# Bing Rewards - Concurrent Multi-Instance Mode

## Overview

Bing Rewards now supports **concurrent execution across multiple browser instances**, allowing you to automate searches on 10+ Chrome profiles simultaneously. This feature dramatically speeds up rewards collection while maintaining resource efficiency.

## Key Features

### 🚀 Concurrent Execution
- Run **10+ browser instances in parallel**
- Configurable concurrency limits
- Automatic resource monitoring and throttling
- Energy-efficient design

### 🔐 Manual Authentication Support
- Pre-authenticate browser profiles manually
- No cookie interference from the script
- Persistent session management
- Support for multiple Microsoft accounts

### 📊 Resource Management
- CPU usage monitoring (default threshold: 80%)
- Memory usage tracking (default threshold: 85%)
- Dynamic throttling based on system load
- Eco mode for conservative resource usage

### 🎯 GUI-Ready Architecture
- Event bus system for decoupled communication
- Callback support for status updates
- Clean API for external control
- Prepared for future web/TCP interface

## Installation

Install with the new dependencies:

```bash
pip install bing-rewards[concurrent]
# or
uv pip install "bing-rewards[concurrent]"
```

Dependencies:
- `psutil>=5.9.0` - Resource monitoring
- `rich>=13.0.0` - Enhanced console output

## Quick Start

### Basic Concurrent Mode

Run with default settings (10 instances max):

```bash
bing-rewards --concurrent
```

### Specify Number of Instances

```bash
bing-rewards --concurrent --max-instances 5
```

### Use Specific Profiles

```bash
bing-rewards --concurrent --profile "Default" "Profile 1" "Profile 2"
```

### Enable Eco Mode

For lower system impact:

```bash
bing-rewards --concurrent --eco-mode
```

### Disable Throttling

If you want maximum speed regardless of resource usage:

```bash
bing-rewards --concurrent --no-throttle
```

## Manual Authentication Workflow

To set up pre-authenticated profiles:

### Step 1: Launch Browsers for Manual Login

```bash
bing-rewards --manual-login --profile "Default" "Profile 1" "Profile 2"
```

This launches browsers without automation. Sign in to each Microsoft account manually.

### Step 2: Close Browsers After Authentication

After signing in, close each browser window manually.

### Step 3: Run Concurrent Automation

```bash
bing-rewards --concurrent --profile "Default" "Profile 1" "Profile 2"
```

The script will use your pre-authenticated sessions.

## Advanced Configuration

### Configuration File

Edit `%APPDATA%\bing-rewards\config.json` (Windows) or `~/.config/bing-rewards/config.json` (Linux/Mac):

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
  "desktop_count": 30,
  "mobile_count": 20,
  "load_delay": 1.5,
  "search_delay": 6.0
}
```

### CLI Options Reference

| Flag | Description | Default |
|------|-------------|---------|
| `-C`, `--concurrent` | Enable concurrent multi-instance mode | Sequential |
| `--max-instances N` | Maximum parallel browser instances | 10 |
| `--list-profiles` | List available Chrome profiles | - |
| `--manual-login` | Launch browsers for manual authentication | - |
| `--no-throttle` | Disable automatic resource throttling | Throttling enabled |
| `--eco-mode` | Conservative resource limits | Normal mode |
| `--instance-timeout SEC` | Timeout per instance (seconds) | 600 |

## Architecture

### Core Components

1. **BrowserManager** - Manages individual browser lifecycle
   - Launch and terminate browsers
   - Execute searches per instance
   - Health monitoring

2. **ConcurrencyController** - Orchestrates parallel execution
   - Thread pool management
   - Resource monitoring
   - Error handling and recovery

3. **ProfileManager** - Handles profile configuration
   - Store/load profile settings
   - Track authentication status
   - Manage search quotas

4. **EventBus** - Decoupled communication
   - Publish/subscribe pattern
   - GUI preparation layer
   - Extensible callbacks

5. **ResourceMonitor** - System resource tracking
   - CPU/memory monitoring
   - Process counting
   - Throttle recommendations

### Execution Flow

```
┌─────────────────────┐
│  ConcurrencyConfig  │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ ConcurrencyController│
└──────────┬──────────┘
           │
    ┌──────┴──────┬──────────────┬────────────┐
    │             │              │            │
┌───▼───┐   ┌────▼────┐   ┌────▼────┐  ┌────▼────┐
│Inst 1 │   │ Inst 2  │   │ Inst 3  │  │ Inst N  │
└───┬───┘   └────┬────┘   └────┬────┘  └────┬────┘
    │            │             │            │
    └────────────┴─────────────┴────────────┘
                 │
          ┌──────▼──────┐
          │ResourceMon. │
          └─────────────┘
```

## Examples

### Example 1: Run 5 Instances with Dry Run

Test without actually searching:

```bash
bing-rewards --concurrent --max-instances 5 --dryrun
```

### Example 2: List Available Profiles

See all Chrome profiles on your system:

```bash
bing-rewards --list-profiles
```

Output:
```
=== Available Chrome Profiles ===
1. Default [DEFAULT]
   Path: C:\Users\You\AppData\Local\Google\Chrome\User Data\Default

2. Profile 1
   Path: C:\Users\You\AppData\Local\Google\Chrome\User Data\Profile 1

3. Profile 2
   Path: C:\Users\You\AppData\Local\Google\Chrome\User Data\Profile 2
```

### Example 3: Eco Mode for Low-End Systems

```bash
bing-rewards --concurrent --eco-mode --max-instances 3
```

### Example 4: Custom Instance Timeout

Set 5-minute timeout per instance:

```bash
bing-rewards --concurrent --instance-timeout 300
```

## Testing

Run the test suite:

```bash
python test_concurrent.py
```

Run integration test:

```bash
python test_concurrent.py --integration --concurrent --max-instances 3 --dryrun
```

## Troubleshooting

### Issue: "No profiles found"

**Solution**: Create Chrome profiles first or specify them explicitly:
```bash
bing-rewards --concurrent --profile "Default"
```

### Issue: High CPU usage

**Solution**: Enable eco mode or reduce instance count:
```bash
bing-rewards --concurrent --eco-mode --max-instances 5
```

### Issue: Browsers not launching

**Solution**: Verify Chrome is installed and on PATH:
```bash
chrome --version
```

Or specify full path:
```bash
bing-rewards --concurrent --exe "C:\Program Files\Google\Chrome\Application\chrome.exe"
```

### Issue: Authentication errors

**Solution**: Use manual login mode to re-authenticate:
```bash
bing-rewards --manual-login --profile "Profile 1"
```

## Performance Tips

1. **Start Small**: Begin with 3-5 instances, then increase
2. **Monitor Resources**: Watch CPU/memory during first run
3. **Use SSD**: Faster profile loading with SSD storage
4. **Close Other Apps**: Free up resources for browser instances
5. **Eco Mode**: Use on laptops or low-end systems

## Backward Compatibility

All existing single-instance commands still work:

```bash
# Legacy sequential mode (unchanged)
bing-rewards --profile "Default" "Profile 1"

# New concurrent mode
bing-rewards --concurrent --profile "Default" "Profile 1"
```

## Future Enhancements

Planned features (GUI integration):
- Web-based dashboard for monitoring
- Real-time progress visualization
- Profile group management
- Scheduling and automation
- Remote control via TCP/WebSocket API

## Technical Details

### Threading Model

The concurrent mode uses a hybrid approach:
- **ThreadPoolExecutor** for I/O-bound operations (search execution)
- **Async coordination** for non-blocking monitoring
- **Process isolation** per browser instance

### Resource Limits

Default thresholds are tuned for typical desktop systems:
- CPU: 80% threshold
- Memory: 85% threshold
- Max processes: 10 Chrome instances

Adjust based on your hardware capabilities.

### Energy Efficiency

Optimizations implemented:
- Batched operations to reduce context switching
- Event-driven architecture (no polling)
- Smart delays based on system load
- Eco mode for conservative limits

## Contributing

Contributions welcome! Areas for improvement:
- Additional resource metrics (GPU, network)
- Better authentication detection
- Profile auto-discovery improvements
- GUI implementation

## License

MIT License - Same as main project
