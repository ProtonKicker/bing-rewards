# SPDX-FileCopyrightText: 2020 jack-mil
#
# SPDX-License-Identifier: MIT

"""Chrome profile discovery and location utilities."""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def get_chrome_user_data_dir() -> Path:
    """Get the Chrome user data directory for the current OS.

    Returns:
        Path to Chrome's user data directory
    """
    if os.name == "nt":  # Windows
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / ".." / "Local" / "Google" / "Chrome" / "User Data"
    elif os.name == "posix":
        # Check for XDG config
        xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        return Path(xdg_config) / "google-chrome"
    else:
        raise OSError(f"Unsupported operating system: {os.name}")


def find_chrome_profiles() -> list[dict]:
    """Find all Chrome profiles on the system.

    Scans the Chrome user data directory and returns information about
    each discovered profile.

    Returns:
        List of dictionaries containing profile information:
        - name: Profile name
        - path: Absolute path to profile directory
        - is_default: Whether this is the Default profile
    """
    try:
        user_data_dir = get_chrome_user_data_dir()
    except OSError as e:
        logger.warning(f"Could not determine Chrome user data directory: {e}")
        return []

    if not user_data_dir.exists():
        logger.warning(f"Chrome user data directory not found: {user_data_dir}")
        return []

    profiles = []

    # Look for profile directories (Default, Profile 1, Profile 2, etc.)
    for item in user_data_dir.iterdir():
        if not item.is_dir():
            continue

        # Check if it's a profile directory
        if item.name == "Default" or item.name.startswith("Profile "):
            profile_info = {
                "name": item.name,
                "path": str(item.absolute()),
                "is_default": item.name == "Default",
            }

            # Try to read profile name from preferences
            prefs_file = item / "Preferences"
            if prefs_file.exists():
                try:
                    with prefs_file.open("r", encoding="utf-8") as f:
                        prefs = json.load(f)
                        profile_name = prefs.get("profile", {}).get("name", item.name)
                        profile_info["display_name"] = profile_name
                except (json.JSONDecodeError, KeyError) as e:
                    logger.debug(f"Could not read profile name for {item.name}: {e}")
                    profile_info["display_name"] = item.name
            else:
                profile_info["display_name"] = item.name

            profiles.append(profile_info)

    # Sort: Default first, then by name
    profiles.sort(key=lambda p: (not p["is_default"], p["name"]))

    logger.info(f"Found {len(profiles)} Chrome profiles")
    return profiles


def find_brave_profiles() -> list[dict]:
    """Find all Brave browser profiles on the system.

    Similar to find_chrome_profiles but for Brave browser.

    Returns:
        List of dictionaries containing profile information
    """
    try:
        if os.name == "nt":  # Windows
            appdata = os.environ.get("APPDATA", "")
            user_data_dir = (
                Path(appdata) / ".." / "Local" / "BraveSoftware" / "Brave-Browser" / "User Data"
            )
        elif os.name == "posix":
            xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
            user_data_dir = Path(xdg_config) / "BraveSoftware" / "Brave-Browser"
        else:
            raise OSError(f"Unsupported operating system: {os.name}")
    except OSError as e:
        logger.warning(f"Could not determine Brave user data directory: {e}")
        return []

    if not user_data_dir.exists():
        logger.warning(f"Brave user data directory not found: {user_data_dir}")
        return []

    profiles = []

    for item in user_data_dir.iterdir():
        if not item.is_dir():
            continue

        if item.name == "Default" or item.name.startswith("Profile "):
            profile_info = {
                "name": item.name,
                "path": str(item.absolute()),
                "is_default": item.name == "Default",
            }

            prefs_file = item / "Preferences"
            if prefs_file.exists():
                try:
                    with prefs_file.open("r", encoding="utf-8") as f:
                        prefs = json.load(f)
                        profile_name = prefs.get("profile", {}).get("name", item.name)
                        profile_info["display_name"] = profile_name
                except (json.JSONDecodeError, KeyError):
                    profile_info["display_name"] = item.name
            else:
                profile_info["display_name"] = item.name

            profiles.append(profile_info)

    profiles.sort(key=lambda p: (not p["is_default"], p["name"]))
    logger.info(f"Found {len(profiles)} Brave profiles")
    return profiles


def list_available_profiles(browser: str = "chrome") -> None:
    """Print available browser profiles to console.

    Args:
        browser: Browser type ("chrome" or "brave")
    """
    if browser.lower() == "chrome":
        profiles = find_chrome_profiles()
    elif browser.lower() == "brave":
        profiles = find_brave_profiles()
    else:
        print(f"Unknown browser type: {browser}")
        return

    if not profiles:
        print(f"No {browser} profiles found.")
        return

    print(f"\n=== Available {browser.title()} Profiles ===")
    for i, profile in enumerate(profiles, 1):
        default_marker = " [DEFAULT]" if profile["is_default"] else ""
        display_name = profile.get("display_name", profile["name"])
        print(f"{i}. {display_name}{default_marker}")
        print(f"   Path: {profile['path']}")
        print()
