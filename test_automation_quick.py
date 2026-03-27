#!/usr/bin/env python3
"""
Quick test to check if automation can start.
This bypasses the GUI and tests the core automation directly.
"""

from bing_rewards.profile_config import ProfileManager
from bing_rewards.app import execute_searches_for_instance, word_generator
from bing_rewards.options import get_options

print("=" * 70)
print("🧪 AUTOMATION QUICK TEST")
print("=" * 70)

# Get profile manager
pm = ProfileManager()
profiles = pm.get_active_profiles()

print(f"\n📂 Found {len(profiles)} profiles")

# Find an isolated profile
isolated = [p for p in profiles if p.is_isolated]
print(f"📂 Found {len(isolated)} isolated profiles")

if not isolated:
    print("\n❌ No isolated profiles found!")
    print("Please create an isolated profile first.")
    exit(1)

# Use first isolated profile
profile = isolated[0]
print(f"\n✅ Using profile: {profile.profile_name}")
print(f"   Path: {profile.user_data_dir}")

# Get options
print("\n⚙️  Loading options...")
options = get_options()
options.desktop_count = 2  # Just 2 for testing
options.mobile_count = 1   # Just 1 for testing
print(f"✅ Desktop searches: {options.desktop_count}")
print(f"✅ Mobile searches: {options.mobile_count}")

# Word generator
print("\n📝 Creating word generator...")
wg = word_generator()
print("✅ Word generator ready")

# Test execution
print("\n🚀 Starting automation test...")
print("   This will launch a browser and execute searches.")
print("   Please wait...")

try:
    from bing_rewards.browser_manager import BrowserInstance

    # Create instance with instance_id and profile
    instance = BrowserInstance(
        instance_id=profile.profile_name,
        profile=profile
    )
    print(f"✅ Browser instance created: {instance.instance_id}")

    # Execute searches
    print("\n📊 Executing searches...")
    searches_completed = execute_searches_for_instance(instance, wg, options, 2, 1)

    # Show results
    print("\n" + "=" * 70)
    print("✅ TEST RESULTS")
    print("=" * 70)
    print(f"Profile: {profile.profile_name}")
    print(f"Searches completed: {searches_completed}")

    if searches_completed > 0:
        print("\n✅ TEST PASSED! Automation is working!")
    else:
        print("\n⚠️  No searches completed (but no errors either)")

    print("=" * 70)

except Exception as e:
    print("\n" + "=" * 70)
    print("❌ TEST FAILED WITH EXCEPTION")
    print("=" * 70)
    print(f"Error: {e}")
    print("\nFull traceback:")
    import traceback
    traceback.print_exc()
    print("=" * 70)
