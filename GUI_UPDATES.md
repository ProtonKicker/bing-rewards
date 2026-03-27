# ✅ GUI Updates: Delete Profiles + Hide Main Browser

## Changes Made

### 1. 🗑️ **Delete Button for Isolated Profiles**

**What Changed:**
- Added a red "🗑️ Delete" button to each isolated profile
- Clicking it shows a confirmation dialog
- On confirmation, the profile is permanently deleted
- Temporary directories are automatically cleaned up

**How to Use:**
1. Find the profile you want to delete
2. Click the "🗑️ Delete" button on the right
3. Confirm the deletion in the popup
4. Profile disappears from the list

**Backend Endpoint:**
```python
POST /api/delete-profile
Body: { "profile_name": "bot-1" }
```

**Frontend Function:**
```javascript
deleteProfile(profileName)
```

---

### 2. 🙈 **Hide "Your Chrome" (Main Browser Profile)**

**What Changed:**
- Regular Chrome profiles (like "Your Chrome") are now **hidden**
- Only **isolated instances** are shown in the profile list
- This keeps the interface clean and focused on bot profiles

**Why:**
- You use your main browser for personal tasks
- Only isolated instances should be used for automation
- Prevents accidental automation of your personal browser

**Before:**
```
☑ Your Chrome (DEFAULT)
☑ 1 (Isolated) ISOLATED
☑ 1112 (Isolated) ISOLATED
☑ b1 (Isolated) ISOLATED
```

**After:**
```
☑ 1 (Isolated) ISOLATED
☑ 1112 (Isolated) ISOLATED
☑ b1 (Isolated) ISOLATED
```

---

### 3. 📝 **Code Changes**

#### Backend (`bing_rewards/gui/app.py`)

**Modified `get_profiles()` function:**
```python
# OLD: Showed all profiles (Chrome + Isolated)
# First add Chrome profiles
for cp in chrome_profiles:
    profiles.append(profile_data)

# Then add isolated profiles
for profile in all_saved_profiles:
    if profile.is_isolated:
        profiles.append(profile_data)

# NEW: Only show isolated profiles
for profile in all_saved_profiles:
    if profile.is_isolated:
        profiles.append(profile_data)
```

**Added `delete_profile()` endpoint:**
```python
@app.route("/api/delete-profile", methods=["POST"])
def delete_profile():
    """Delete an isolated profile."""
    data = request.json
    profile_name = data.get("profile_name")
    
    if not profile_name:
        return jsonify({"error": "Profile name required"}), 400
    
    profile = gui_state["profile_manager"].get_profile(profile_name)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    
    if not profile.is_isolated:
        return jsonify({"error": "Can only delete isolated profiles"}), 400
    
    # Delete the profile (removes temp directory)
    gui_state["profile_manager"].remove_profile(profile_name)
    
    logger.info(f"Deleted profile: {profile_name}")
    return jsonify({"status": "success", "message": f"Profile '{profile_name}' deleted"})
```

#### Frontend (`bing_rewards/gui/templates/gui.html`)

**Added CSS for delete button:**
```css
.profile-actions {
    display: flex;
    gap: 8px;
    margin-left: auto;
}

.btn-delete {
    padding: 6px 12px;
    background: #ef4444;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    transition: all 0.2s;
}

.btn-delete:hover {
    background: #dc2626;
    transform: scale(1.05);
}
```

**Modified profile rendering:**
```javascript
profiles.forEach(profile => {
    const item = document.createElement('div');
    item.className = 'profile-item';
    
    // Only show isolated profiles (hide regular Chrome profiles)
    if (!profile.is_isolated) {
        return; // Skip non-isolated profiles
    }
    
    item.innerHTML = `
        <input type="checkbox" id="profile_${profile.name}" value="${profile.name}">
        <div class="profile-info">
            <div class="profile-name">
                ${profile.display_name}
                <span class="badge" style="background: #10b981;">ISOLATED</span>
            </div>
            <div class="profile-path">${profile.path}</div>
            ${profile.is_temporary ? '<div style="font-size: 11px; color: #f59e0b; margin-top: 4px;">⚠️ Temporary (auto-cleanup)</div>' : ''}
        </div>
        <div class="profile-actions">
            <button class="btn-delete" onclick="deleteProfile('${profile.name}')">
                🗑️ Delete
            </button>
        </div>
    `;
    // ... rest of code
});
```

**Added delete function:**
```javascript
async function deleteProfile(profileName) {
    if (!confirm(`Are you sure you want to delete profile "${profileName}"?\n\nThis will permanently delete the profile and all its data.`)) {
        return;
    }

    try {
        const response = await fetch('/api/delete-profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profile_name: profileName }),
        });

        const result = await response.json();
        if (response.ok) {
            addEvent('SUCCESS', `Profile '${profileName}' deleted`);
            // Remove from selected profiles
            selectedProfiles.delete(profileName);
            // Refresh the list
            refreshProfiles();
        } else {
            addEvent('ERROR', result.error || 'Failed to delete profile');
        }
    } catch (error) {
        addEvent('ERROR', 'Failed to delete profile');
        console.error(error);
    }
}
```

---

## 🧪 Testing

### Test 1: Delete a Profile

1. **Start GUI** (after restart):
   ```bash
   python -m bing_rewards.gui
   ```

2. **Find a test profile** to delete (e.g., "test-1")

3. **Click "🗑️ Delete"** button next to it

4. **Confirm deletion** in the popup

5. **Expected Result:**
   - ✅ Confirmation dialog appears
   - ✅ Event log shows: "Profile 'test-1' deleted"
   - ✅ Profile disappears from list
   - ✅ Temporary directory is deleted

### Test 2: Main Browser Hidden

1. **Refresh profiles** in GUI

2. **Check profile list**

3. **Expected Result:**
   - ✅ "Your Chrome" is NOT visible
   - ✅ Only isolated instances are shown
   - ✅ All profiles have "ISOLATED" badge

---

## 📊 Visual Changes

### Before:
```
┌─────────────────────────────────────────┐
│ Select Profiles                         │
├─────────────────────────────────────────┤
│ ☑ Your Chrome (DEFAULT)                 │
│   C:\Users\...\Chrome\User Data\Default │
│                                         │
│ ☑ 1 (Isolated) [ISOLATED]               │
│   C:\Users\...\Temp\bing_rewards_1_...  │
│   ⚠️ Temporary (auto-cleanup)           │
│                                         │
│ ☑ bot-1 (Isolated) [ISOLATED]           │
│   C:\Users\...\Temp\bing_rewards_bot-1  │
│   ⚠️ Temporary (auto-cleanup)           │
└─────────────────────────────────────────┘
```

### After:
```
┌─────────────────────────────────────────┐
│ Select Profiles                         │
├─────────────────────────────────────────┤
│ ☑ 1 (Isolated) [ISOLATED]     🗑️ Delete │
│   C:\Users\...\Temp\bing_rewards_1_...  │
│   ⚠️ Temporary (auto-cleanup)           │
│                                         │
│ ☑ bot-1 (Isolated) [ISOLATED] 🗑️ Delete │
│   C:\Users\...\Temp\bing_rewards_bot-1  │
│   ⚠️ Temporary (auto-cleanup)           │
└─────────────────────────────────────────┘
```

**Changes:**
- ❌ "Your Chrome" is hidden
- ✅ Delete button added to each profile

---

## ⚠️ Important Notes

### Profile Deletion is PERMANENT

**What Gets Deleted:**
- Profile configuration
- Browser cookies and sessions
- Login credentials
- Temporary directory
- All profile data

**Warning:**
> Once deleted, you cannot recover the profile. You'll need to create a new one and log in again.

### Temporary Directory Cleanup

When you delete a temporary profile:
1. Profile is removed from `profiles.json`
2. Temporary directory is deleted automatically
3. Disk space is freed

**Example:**
```
Before deletion:
C:\Users\...\Temp\bing_rewards_bot-1_abc123\

After deletion:
Directory no longer exists
```

---

## 🔧 How to Restart GUI

**Important:** You MUST restart the GUI for changes to take effect!

### Method 1: Ctrl+C

1. In terminal running GUI
2. Press **Ctrl+C**
3. Wait for it to stop
4. Run: `python -m bing_rewards.gui`

### Method 2: Close Terminal

1. Close the terminal window
2. Open new terminal
3. Run: `python -m bing_rewards.gui`

### Method 3: Use Batch File

1. Double-click: `launch-gui.bat`
2. (It automatically restarts)

---

## ✅ Success Checklist

After restarting, verify:

- [ ] GUI loads at http://localhost:5000
- [ ] "Your Chrome" is NOT visible
- [ ] Only isolated instances are shown
- [ ] Each profile has a "🗑️ Delete" button
- [ ] Clicking delete shows confirmation dialog
- [ ] Confirming deletion removes the profile
- [ ] Profile disappears from list
- [ ] Event log shows deletion success message

---

## 🎯 Usage Example

### Scenario: Clean Up Old Test Profiles

**Before:**
```
You have 10 profiles:
- Your Chrome (personal browser)
- test-1, test-2, test-3 (old tests)
- bot-1, bot-2, bot-3 (active bots)
- old-1, old-2, old-3 (unused)
```

**Clean Up Steps:**

1. **Delete test profiles:**
   - Click "🗑️ Delete" on test-1
   - Click "🗑️ Delete" on test-2
   - Click "🗑️ Delete" on test-3

2. **Delete old profiles:**
   - Click "🗑️ Delete" on old-1
   - Click "🗑️ Delete" on old-2
   - Click "🗑️ Delete" on old-3

**After:**
```
You have 4 profiles:
- bot-1, bot-2, bot-3 (active bots)
```

**Result:**
- ✅ Clean profile list
- ✅ Freed disk space
- ✅ No personal browser mixing
- ✅ Only active bot profiles remain

---

## 🛡️ Safety Features

### 1. Confirmation Dialog

**Prevents accidental deletion:**
```
┌─────────────────────────────────────────┐
│ Are you sure you want to delete profile │
│ "bot-1"?                                │
│                                         │
│ This will permanently delete the        │
│ profile and all its data.               │
│                                         │
│  [Cancel]  [OK]                         │
└─────────────────────────────────────────┘
```

### 2. Only Isolated Profiles Can Be Deleted

**Backend validation:**
```python
if not profile.is_isolated:
    return jsonify({"error": "Can only delete isolated profiles"}), 400
```

This prevents accidental deletion of Chrome profiles.

### 3. Error Handling

**If deletion fails:**
- Error shown in Event Log
- Profile remains in list
- No data corruption

---

## 📝 Files Modified

1. **`bing_rewards/gui/app.py`**
   - Modified `get_profiles()` to hide Chrome profiles
   - Added `delete_profile()` endpoint

2. **`bing_rewards/gui/templates/gui.html`**
   - Added delete button CSS
   - Modified profile rendering
   - Added `deleteProfile()` JavaScript function

---

## 🚀 Next Steps

1. **Restart GUI**: `python -m bing_rewards.gui`
2. **Verify changes**: Check that only isolated instances show
3. **Test delete**: Delete a test profile
4. **Enjoy clean interface!**

---

**Summary:**
- ✅ Delete button added to isolated profiles
- ✅ Main browser profile is hidden
- ✅ Only isolated instances are shown
- ✅ Automatic cleanup of temporary directories
- ✅ Confirmation dialog prevents accidents
- ✅ Changes require GUI restart to take effect

**Restart command:**
```bash
python -m bing_rewards.gui
```

