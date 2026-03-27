#!/usr/bin/env python3
"""
DIRECT TEST - Bypass everything and test the actual search execution
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from bing_rewards.profile_config import ProfileManager
from bing_rewards.browser_manager import BrowserManager, BrowserInstance
from bing_rewards.app import word_generator, execute_searches_for_instance
from bing_rewards.options import get_options

print("=" * 70)
print("DIRECT SEARCH TEST - Testing actual search execution")
print("=" * 70)

# Get an isolated profile
pm = ProfileManager()
profiles = pm.get_active_profiles()
isolated = [p for p in profiles if p.is_isolated]

if not isolated:
    print("\n❌ No isolated profiles! Create one first!")
    sys.exit(1)

profile = isolated[0]
print(f"\n✅ Using profile: {profile.profile_name}")
print(f"   Path: {profile.user_data_dir}")

# Get options
options = get_options()
options.desktop_count = 2
options.mobile_count = 1

print(f"\n⚙️  Config: {options.desktop_count} desktop, {options.mobile_count} mobile")

# Create browser manager
browser_mgr = BrowserManager()

print("\n🚀 Creating browser instance...")
instance = browser_mgr.create_instance("test-direct", profile)

print("🚀 Launching browser...")
success = instance.launch(
    browser_path=None,  # Use default Chrome
    agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    load_delay=3,
    dry_run=False,
)

if not success:
    print("❌ Failed to launch browser!")
    sys.exit(1)

print("✅ Browser launched successfully!")
print("\n📊 Executing searches...")

try:
    wg = word_generator()
    result = execute_searches_for_instance(instance, wg, options, 2, 1)
    print(f"\n✅ SEARCHES COMPLETED: {result}")
except Exception as e:
    print(f"\n❌ ERROR during search execution: {e}")
    import traceback
    traceback.print_exc()

print("\n🏁 Cleaning up...")
browser_mgr.shutdown_all()
print("✅ Done!")
