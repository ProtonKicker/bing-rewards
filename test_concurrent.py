#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2020 jack-mil
#
# SPDX-License-Identifier: MIT

"""Test script for concurrent Bing Rewards execution.

This script demonstrates the new multi-instance concurrent execution capability.
Run this to verify the implementation works correctly.

Usage:
    python test_concurrent.py --help
    python test_concurrent.py --concurrent --max-instances 5
    python test_concurrent.py --list-profiles
    python test_concurrent.py --manual-login
"""

import sys
from pathlib import Path

# Add parent directory to path to import bing_rewards
sys.path.insert(0, str(Path(__file__).parent))

from bing_rewards.app import main
from bing_rewards.options import get_options


def print_banner():
    """Print test banner."""
    print("=" * 70)
    print("Bing Rewards - Concurrent Multi-Instance Test")
    print("=" * 70)
    print()


def test_basic_imports():
    """Test that all new modules can be imported."""
    print("Testing imports...")
    try:
        from bing_rewards.browser_manager import BrowserInstance, BrowserManager, BrowserState
        from bing_rewards.concurrency_controller import ConcurrencyController, ConcurrencyConfig
        from bing_rewards.event_bus import EventBus, EventType
        from bing_rewards.profile_config import ProfileConfig, ProfileManager
        from bing_rewards.resource_monitor import ResourceMonitor, ResourceLimits
        from bing_rewards.utils.chrome_finder import find_chrome_profiles
        from bing_rewards.utils.session_checker import SessionChecker

        print("[OK] All imports successful")
        return True
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        return False


def test_profile_discovery():
    """Test Chrome profile discovery."""
    print("\nTesting profile discovery...")
    try:
        from bing_rewards.utils.chrome_finder import find_chrome_profiles

        profiles = find_chrome_profiles()
        if profiles:
            print(f"[OK] Found {len(profiles)} Chrome profiles:")
            for i, profile in enumerate(profiles[:5], 1):  # Show first 5
                display_name = profile.get("display_name", profile["name"])
                print(f"  {i}. {display_name}")
            if len(profiles) > 5:
                print(f"  ... and {len(profiles) - 5} more")
        else:
            print("⚠ No Chrome profiles found (this is OK if Chrome is not installed)")
        return True
    except Exception as e:
        print(f"✗ Profile discovery failed: {e}")
        return False


def test_resource_monitor():
    """Test resource monitoring."""
    print("\nTesting resource monitor...")
    try:
        from bing_rewards.resource_monitor import ResourceMonitor, ResourceLimits

        limits = ResourceLimits(cpu_threshold=80.0, memory_threshold=85.0, max_processes=10)
        monitor = ResourceMonitor(limits)
        stats = monitor.get_stats()

        print("[OK] Resource monitor working:")
        print(f"  CPU: {stats['cpu_percent']:.1f}%")
        print(f"  Memory: {stats['memory_percent']:.1f}%")
        print(f"  Available: {stats['memory_available_mb']:.0f} MB")
        print(f"  Within limits: {monitor.is_within_limits()}")
        return True
    except ImportError:
        print("⚠ psutil not installed (install with: pip install psutil)")
        return True  # Not a critical failure
    except Exception as e:
        print(f"✗ Resource monitor failed: {e}")
        return False


def test_event_bus():
    """Test event bus system."""
    print("\nTesting event bus...")
    try:
        from bing_rewards.event_bus import EventBus, EventType

        bus = EventBus()
        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe(EventType.INSTANCE_LAUNCHED, handler)
        bus.emit(
            EventType.INSTANCE_LAUNCHED,
            source="test",
            instance_id="test_1",
            profile_name="Test Profile",
        )

        if len(events_received) == 1:
            print("[OK] Event bus working correctly")
            return True
        else:
            print(f"✗ Event bus issue: expected 1 event, got {len(events_received)}")
            return False
    except Exception as e:
        print(f"✗ Event bus failed: {e}")
        return False


def test_profile_config():
    """Test profile configuration management."""
    print("\nTesting profile configuration...")
    try:
        from bing_rewards.profile_config import ProfileConfig, ProfileManager

        # Test creating a profile config
        profile = ProfileConfig(
            profile_name="TestProfile",
            is_authenticated=False,
            priority=1,
        )

        # Test serialization
        profile_dict = profile.to_dict()
        restored = ProfileConfig.from_dict(profile_dict)

        if restored.profile_name == profile.profile_name:
            print("[OK] Profile configuration working")
            return True
        else:
            print("✗ Profile serialization issue")
            return False
    except Exception as e:
        print(f"✗ Profile configuration failed: {e}")
        return False


def run_integration_test(options_str: list[str]):
    """Run integration test with actual execution.

    Args:
        options_str: List of command-line arguments
    """
    print("\n" + "=" * 70)
    print("Integration Test - Running with options:", " ".join(options_str))
    print("=" * 70)
    print()
    print("This will launch the actual bing-rewards application.")
    print("Use --dryrun to test without actually searching.")
    print()

    # Temporarily modify sys.argv
    old_argv = sys.argv.copy()
    try:
        sys.argv = ["bing-rewards"] + options_str
        main()
        print("\n[OK] Integration test completed successfully")
        return True
    except SystemExit as e:
        if e.code == 0:
            print("\n[OK] Integration test completed (exit code 0)")
            return True
        else:
            print(f"\n[FAIL] Integration test exited with code: {e.code}")
            return False
    except Exception as e:
        print(f"\n[FAIL] Integration test failed: {e}")
        return False
    finally:
        sys.argv = old_argv


def main_test():
    """Run all tests."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Test concurrent Bing Rewards execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_concurrent.py                    # Run unit tests only
  python test_concurrent.py --integration      # Run integration test
  python test_concurrent.py --integration --concurrent --max-instances 5
  python test_concurrent.py --list-profiles    # List available profiles
        """,
    )

    parser.add_argument(
        "--integration",
        action="store_true",
        help="Run integration test with actual browser execution",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all tests including integration",
    )
    parser.add_argument(
        "--skip-unit",
        action="store_true",
        help="Skip unit tests",
    )

    # Parse known args only (ignore extra args for integration mode)
    args, remaining = parser.parse_known_args()

    print_banner()

    results = {}

    # Unit tests
    if not args.skip_unit:
        print("\n=== Running Unit Tests ===\n")
        results["imports"] = test_basic_imports()
        results["profile_discovery"] = test_profile_discovery()
        results["resource_monitor"] = test_resource_monitor()
        results["event_bus"] = test_event_bus()
        results["profile_config"] = test_profile_config()

    # Integration test
    if args.integration or args.all:
        print("\n=== Running Integration Test ===\n")
        integration_args = ["--dryrun"]
        if remaining:
            integration_args.extend(remaining)
        results["integration"] = run_integration_test(integration_args)

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    total = len(results)
    passed = sum(results.values())
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n[OK] All tests passed!")
        return 0
    else:
        print("\n[FAIL] Some tests failed:")
        for test, result in results.items():
            if not result:
                print(f"  - {test}")
        return 1


if __name__ == "__main__":
    sys.exit(main_test())
