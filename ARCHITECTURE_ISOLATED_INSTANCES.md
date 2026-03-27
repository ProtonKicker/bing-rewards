# Isolated Instances Architecture

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Bing Rewards GUI                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Web Interface (Flask + HTML/JS)                        │   │
│  │  - Create Isolated Instance Button                      │   │
│  │  - Profile Selection Checkboxes                         │   │
│  │  - Start/Stop Controls                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  REST API Endpoints                                     │   │
│  │  POST /api/create-isolated-profile                      │   │
│  │  GET  /api/profiles                                     │   │
│  │  POST /api/start                                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Profile Management Layer                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ProfileManager.create_isolated_profile()               │   │
│  │  - Creates temp directory                               │   │
│  │  - Sets is_isolated=True                                │   │
│  │  - Sets is_temporary=True                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ProfileConfig Objects                                  │   │
│  │  - profile_name: "bot-1"                                │   │
│  │  - user_data_dir: /tmp/bing_rewards_bot-1_xyz/          │   │
│  │  - is_isolated: True                                    │   │
│  │  - is_temporary: True                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Browser Execution Layer                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  BrowserInstance._build_command()                       │   │
│  │  Detects is_isolated=True → Adds flags:                 │   │
│  │    ✓ --user-data-dir="/tmp/..."                         │   │
│  │    ✓ --disable-extensions                               │   │
│  │    ✓ --disable-background-networking                    │   │
│  │    ✓ --disable-default-apps                             │   │
│  │    ✓ --no-first-run                                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Chromium Process                                       │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │  Isolated Browser Session                       │    │   │
│  │  │  - No access to Chrome profiles                 │    │   │
│  │  │  - No extensions                                │    │   │
│  │  │  - Clean cookies/cache                          │    │   │
│  │  │  - Temporary storage only                       │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Cleanup Layer                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  BrowserInstance.close()                                │   │
│  │  - Detects is_temporary=True                            │   │
│  │  - Calls _cleanup_temporary_directory()                 │   │
│  │  - Deletes entire temp directory tree                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Temporary Directory Removed ✓                          │   │
│  │  - All cookies deleted                                  │   │
│  │  - All cache deleted                                    │   │
│  │  - All history deleted                                  │   │
│  │  - No trace left behind                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow: Creating an Isolated Instance

```
User Action: Click "Create New Isolated Instance"
         │
         ▼
┌──────────────────────────────────────────┐
│  GUI: createIsolatedProfile()            │
│  - Prompts for name: "bot-1"             │
│  - POST /api/create-isolated-profile     │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  Flask API: create_isolated_profile()    │
│  - Receives: {name: "bot-1"}             │
│  - Calls: ProfileManager.create_isolated │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  ProfileManager.create_isolated_profile()│
│  1. Creates temp directory:              │
│     /tmp/bing_rewards_bot-1_abc123/      │
│  2. Creates user_data subdirectory       │
│  3. Returns ProfileConfig:               │
│     {                                    │
│       profile_name: "bot-1",             │
│       user_data_dir: Path(...),          │
│       is_isolated: True,                 │
│       is_temporary: True                 │
│     }                                    │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  Save to ProfileManager                  │
│  - Adds to profiles dictionary           │
│  - Persists to profiles.json             │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  Return to GUI                           │
│  - Status: success                       │
│  - Profile info: {                       │
│      name: "bot-1",                      │
│      path: "/tmp/...",                   │
│      is_isolated: True,                  │
│      is_temporary: True                  │
│    }                                     │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  GUI Updates Profile List                │
│  - Shows profile with checkbox           │
│  - Green "ISOLATED" badge                │
│  - Orange "⚠️ Temporary" warning         │
└──────────────────────────────────────────┘
```

## Browser Launch Flow

```
User Action: Click "Start" with isolated profile selected
         │
         ▼
┌──────────────────────────────────────────┐
│  ConcurrencyController.run_concurrent()  │
│  - Iterates through selected profiles    │
│  - Creates BrowserInstance for each      │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  BrowserInstance.__init__()              │
│  - instance_id: "bot-1"                  │
│  - profile: ProfileConfig object         │
│  - state: BrowserState.CREATED           │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  BrowserInstance.launch()                │
│  - Sets state: LAUNCHING                 │
│  - Calls: _build_command()               │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  _build_command() - Isolation Detection  │
│  if profile.is_isolated:                 │
│    ✓ Add --user-data-dir="/tmp/..."      │
│    ✓ Add --disable-extensions            │
│    ✓ Add --disable-background-networking │
│    ✓ Add --disable-default-apps          │
│    ✓ Add --no-first-run                  │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  subprocess.Popen(command)               │
│  - Launches Chromium process             │
│  - PID: 12345                            │
│  - State: RUNNING                        │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  Browser Executes Searches               │
│  - Uses pynput for keyboard simulation   │
│  - Types search queries                  │
│  - Tracks progress                       │
└──────────────────────────────────────────┘
```

## Cleanup Flow

```
User Action: Click "Stop" OR searches complete
         │
         ▼
┌──────────────────────────────────────────┐
│  BrowserInstance.close()                 │
│  - Terminates process (taskkill/kill)    │
│  - State: TERMINATED                     │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  Check: profile.is_temporary == True     │
│  AND profile.user_data_dir exists        │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  _cleanup_temporary_directory()          │
│  - Gets temp_dir = user_data_dir.parent  │
│  - Calls: shutil.rmtree(temp_dir)        │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  Directory Deletion                      │
│  /tmp/bing_rewards_bot-1_abc123/         │
│  ├── user_data/                          │
│  │   ├── Default/                        │
│  │   ├── Cache/                          │
│  │   ├── Cookies                         │
│  │   └── Local Storage/                  │
│  └── (all deleted ✓)                     │
└──────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  Log Event                               │
│  "Cleaning up temporary directory: ..."  │
│  "Browser [12345] closed successfully"   │
└──────────────────────────────────────────┘
```

## Profile Type Comparison

```
┌─────────────────────────────────────────────────────────────┐
│  CHROME PROFILE (Traditional)                               │
├─────────────────────────────────────────────────────────────┤
│  Location: C:\Users\You\AppData\Local\Google\Chrome\...     │
│  Persistence: Permanent                                     │
│  Extensions: ✓ Enabled                                      │
│  Cookies: ✓ Saved                                           │
│  History: ✓ Saved                                           │
│  Bookmarks: ✓ Synced                                        │
│  Passwords: ✓ Saved                                         │
│  Cleanup: Manual (if needed)                                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  ISOLATED PROFILE (New)                                     │
├─────────────────────────────────────────────────────────────┤
│  Location: C:\Users\You\AppData\Local\Temp\bing_rewards_... │
│  Persistence: Temporary (auto-deleted)                      │
│  Extensions: ✗ Disabled                                     │
│  Cookies: ✗ Session only (deleted)                          │
│  History: ✗ Not saved                                       │
│  Bookmarks: ✗ None                                          │
│  Passwords: ✗ Not saved                                     │
│  Cleanup: Automatic ✓                                       │
└─────────────────────────────────────────────────────────────┘
```

## File System Structure

```
Before Launch:
┌─────────────────────────────────────────┐
│  System Temp Directory                  │
│  C:\Users\You\AppData\Local\Temp\       │
│                                         │
│  (No bing_rewards directories yet)      │
└─────────────────────────────────────────┘

After Creating Isolated Profile:
┌─────────────────────────────────────────┐
│  System Temp Directory                  │
│  C:\Users\You\AppData\Local\Temp\       │
│                                         │
│  ├── bing_rewards_bot-1_abc123/         │
│  │   └── user_data/                     │
│  │       └── (empty, waiting for Chrome)│
│  │                                      │
│  ├── bing_rewards_bot-2_def456/         │
│  │   └── user_data/                     │
│  │       └── (empty, waiting for Chrome)│
│  └── ...                                │
└─────────────────────────────────────────┘

During Browser Execution:
┌─────────────────────────────────────────┐
│  System Temp Directory                  │
│  C:\Users\You\AppData\Local\Temp\       │
│                                         │
│  ├── bing_rewards_bot-1_abc123/         │
│  │   └── user_data/                     │
│  │       ├── Default/                   │
│  │       │   ├── Cookies                │
│  │       │   ├── History                │
│  │       │   └── Local Storage/         │
│  │       ├── Cache/                     │
│  │       └── Crash Reports/             │
│  │                                      │
│  └── bing_rewards_bot-2_def456/         │
│      └── user_data/                     │
│          └── (similar structure)        │
└─────────────────────────────────────────┘

After Cleanup:
┌─────────────────────────────────────────┐
│  System Temp Directory                  │
│  C:\Users\You\AppData\Local\Temp\       │
│                                         │
│  (bing_rewards directories deleted ✓)   │
│                                         │
│  (No trace left behind)                 │
└─────────────────────────────────────────┘
```

## Command Line Arguments

### Isolated Profile Command

```bash
chrome.exe \
  --new-window \
  --user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..." \
  --user-data-dir="C:\Users\...\Temp\bing_rewards_bot-1_abc123\user_data" \
  --disable-extensions \
  --disable-background-networking \
  --disable-default-apps \
  --no-first-run
```

### Chrome Profile Command (for comparison)

```bash
chrome.exe \
  --new-window \
  --user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..." \
  --profile-directory="Default"
```

**Key Differences:**
- Isolated: Uses `--user-data-dir` with temp path
- Chrome: Uses `--profile-directory` with profile name
- Isolated: Adds 4 isolation flags
- Chrome: No isolation flags

## State Machine

```
BrowserInstance State Transitions:

    CREATED
       │
       │ launch()
       ▼
  LAUNCHING
       │
       │ process started
       ▼
   RUNNING
       │
       │ execute_searches()
       ▼
  SEARCHING
       │
       │ searches complete
       ▼
  COMPLETED
       │
       │ close()
       ▼
 TERMINATED
       │
       │ cleanup (if temporary)
       ▼
   CLEANED UP
```

## Error Handling

```
┌──────────────────────────────────────────┐
│  Error: Failed to create temp directory  │
├──────────────────────────────────────────┤
│  Detection: tempfile.mkdtemp() fails     │
│  Response: Return error to GUI           │
│  Message: "Failed to create profile"     │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  Error: Chrome not found                 │
├──────────────────────────────────────────┤
│  Detection: FileNotFoundError            │
│  Response: Log error, mark instance FAIL │
│  Message: "Browser executable not found" │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  Error: Cleanup failed                   │
├──────────────────────────────────────────┤
│  Detection: shutil.rmtree() fails        │
│  Response: Log warning, continue         │
│  Message: "Failed to cleanup directory"  │
│  Action: Manual cleanup may be needed    │
└──────────────────────────────────────────┘
```

## Security Model

```
┌──────────────────────────────────────────┐
│  Isolation Boundary                      │
├──────────────────────────────────────────┤
│  ✓ Separate Process Space                │
│  ✓ Separate User Data Directory          │
│  ✓ No Access to Chrome Profiles          │
│  ✓ No Extension Loading                  │
│  ✓ Clean Cookie Store                    │
│  ✓ Clean Local Storage                   │
│  ✓ Clean Cache                           │
│  ✓ No Password Manager                   │
│  ✓ No Sync with Google Account           │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  Temporary Storage Security              │
├──────────────────────────────────────────┤
│  ✓ Random Directory Names                │
│     (bing_rewards_bot-1_abc123)          │
│  ✓ System Temp Location                  │
│     (OS-managed, secure)                 │
│  ✓ Auto-Deletion on Close                │
│     (no persistent data)                 │
│  ✓ Complete Directory Removal            │
│     (shutil.rmtree)                      │
└──────────────────────────────────────────┘
```

This architecture ensures:
- ✅ Complete isolation from personal Chrome
- ✅ Automatic cleanup of all temporary data
- ✅ No persistent sensitive information
- ✅ Scalable to 10+ concurrent instances
- ✅ Secure, privacy-preserving automation
