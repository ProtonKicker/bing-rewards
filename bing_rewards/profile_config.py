# SPDX-FileCopyrightText: 2020 jack-mil
#
# SPDX-License-Identifier: MIT

"""Profile configuration and management for multi-instance browser automation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TypedDict


class SearchQuota(TypedDict):
    """Type definition for search quota tracking."""

    desktop_remaining: int
    mobile_remaining: int
    last_reset: str  # ISO format datetime string


@dataclass
class ProfileConfig:
    """Configuration for a single browser profile.

    Attributes:
        profile_name: Name of the Chrome profile (e.g., "Default", "Profile 1")
        user_data_dir: Absolute path to the profile's user data directory
        is_authenticated: Whether the profile has valid MS account cookies
        last_used: Last time this profile was used for automation
        search_quota: Dictionary tracking remaining searches for desktop/mobile
        is_active: Whether this profile should be used in concurrent execution
        priority: Execution priority (lower number = higher priority)
        is_temporary: If True, use temporary directory that's deleted on close
        is_isolated: If True, creates independent Chromium instance (no extensions, clean session)
    """

    profile_name: str
    user_data_dir: Path | None = None
    is_authenticated: bool = False
    last_used: datetime | None = None
    search_quota: SearchQuota = field(
        default_factory=lambda: SearchQuota(
            desktop_remaining=30, mobile_remaining=20, last_reset=""
        )
    )
    is_active: bool = True
    priority: int = 0
    is_temporary: bool = False
    is_isolated: bool = True

    def to_dict(self) -> dict:
        """Convert ProfileConfig to dictionary for JSON serialization."""
        return {
            "profile_name": self.profile_name,
            "user_data_dir": str(self.user_data_dir) if self.user_data_dir else None,
            "is_authenticated": self.is_authenticated,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "search_quota": self.search_quota,
            "is_active": self.is_active,
            "priority": self.priority,
            "is_temporary": self.is_temporary,
            "is_isolated": self.is_isolated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProfileConfig:
        """Create ProfileConfig from dictionary."""
        return cls(
            profile_name=data["profile_name"],
            user_data_dir=Path(data["user_data_dir"])
            if data.get("user_data_dir")
            else None,
            is_authenticated=data.get("is_authenticated", False),
            last_used=datetime.fromisoformat(data["last_used"])
            if data.get("last_used")
            else None,
            search_quota=data.get(
                "search_quota",
                SearchQuota(desktop_remaining=30, mobile_remaining=20, last_reset=""),
            ),
            is_active=data.get("is_active", True),
            priority=data.get("priority", 0),
            is_temporary=data.get("is_temporary", False),
            is_isolated=data.get("is_isolated", True),
        )

    def update_last_used(self):
        """Update the last_used timestamp to now."""
        self.last_used = datetime.now()

    def reset_quota(self, desktop: int = 30, mobile: int = 20):
        """Reset the search quota."""
        self.search_quota = SearchQuota(
            desktop_remaining=desktop,
            mobile_remaining=mobile,
            last_reset=datetime.now().isoformat(),
        )

    def has_quota(self) -> bool:
        """Check if profile has remaining search quota."""
        return (
            self.search_quota["desktop_remaining"] > 0
            or self.search_quota["mobile_remaining"] > 0
        )


class ProfileManager:
    """Manages multiple browser profiles for concurrent execution.

    Handles loading, saving, and organizing Chrome profiles with their
    authentication state and search quotas.
    """

    def __init__(self, config_file: Path | None = None):
        """Initialize profile manager.

        Args:
            config_file: Path to profile configuration JSON file.
                        If None, uses default location.
        """
        if config_file is None:
            from bing_rewards.options import config_location

            self.config_file = config_location().parent / "profiles.json"
        else:
            self.config_file = config_file

        self.profiles: dict[str, ProfileConfig] = {}
        self.load()

    def load(self) -> None:
        """Load profiles from configuration file."""
        if not self.config_file.exists():
            return

        try:
            with self.config_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                for name, profile_data in data.get("profiles", {}).items():
                    self.profiles[name] = ProfileConfig.from_dict(profile_data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not load profiles: {e}")

    def save(self) -> None:
        """Save profiles to configuration file."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "profiles": {
                name: profile.to_dict() for name, profile in self.profiles.items()
            },
            "last_updated": datetime.now().isoformat(),
        }

        with self.config_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add_profile(self, profile: ProfileConfig) -> None:
        """Add or update a profile."""
        self.profiles[profile.profile_name] = profile
        self.save()

    def get_profile(self, name: str) -> ProfileConfig | None:
        """Get a profile by name."""
        return self.profiles.get(name)

    def get_active_profiles(self) -> list[ProfileConfig]:
        """Get all active profiles sorted by priority."""
        return sorted(
            [p for p in self.profiles.values() if p.is_active],
            key=lambda x: (x.priority, x.profile_name),
        )

    def remove_profile(self, name: str) -> None:
        """Remove a profile."""
        if name in self.profiles:
            del self.profiles[name]
            self.save()

    def list_profiles(self) -> list[str]:
        """List all profile names."""
        return list(self.profiles.keys())

    def update_authentication_status(
        self, profile_name: str, is_authenticated: bool
    ) -> None:
        """Update authentication status for a profile."""
        if profile_name in self.profiles:
            self.profiles[profile_name].is_authenticated = is_authenticated
            self.save()

    def get_authenticated_profiles(self) -> list[ProfileConfig]:
        """Get only authenticated profiles."""
        return [p for p in self.profiles.values() if p.is_authenticated and p.is_active]

    @staticmethod
    def create_isolated_profile(
        name: str, base_dir: Path | None = None, temporary: bool = True
    ) -> ProfileConfig:
        """Create a new isolated profile with its own user data directory.

        Args:
            name: Profile name/identifier
            base_dir: Base directory for profiles. If None, uses temp directory
            temporary: If True, profile will be marked for cleanup

        Returns:
            ProfileConfig for the new isolated profile
        """
        import tempfile

        if base_dir is None or temporary:
            # Create temporary directory
            temp_dir = Path(tempfile.mkdtemp(prefix=f"bing_rewards_{name}_"))
            user_data_dir = temp_dir / "user_data"
            user_data_dir.mkdir(parents=True, exist_ok=True)
        else:
            # Use persistent directory
            base_dir = Path(base_dir)
            base_dir.mkdir(parents=True, exist_ok=True)
            user_data_dir = base_dir / name

        return ProfileConfig(
            profile_name=name,
            user_data_dir=user_data_dir,
            is_temporary=temporary,
            is_isolated=True,
        )
