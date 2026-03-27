# SPDX-FileCopyrightText: 2020 jack-mil
#
# SPDX-License-Identifier: MIT

"""Session and authentication validation for browser profiles."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class SessionChecker:
    """Checks and validates Microsoft account authentication in browser profiles.

    Examines Chrome profile cookies and local storage to determine if a
    profile has valid Microsoft account authentication for Bing Rewards.
    """

    # Microsoft-related cookie names that indicate authentication
    MS_AUTH_COOKIES = [
        "RPSSecAuth",
        "RPSAuth",
        "WLSSecure",
        "WLS",
        "MSPReauth",
        "ESTSAUTHPERSISTENT",
    ]

    # Minimum number of MS cookies needed for valid auth
    MIN_AUTH_COOKIES = 2

    def __init__(self, profile_path: Path | str):
        """Initialize session checker.

        Args:
            profile_path: Path to Chrome profile directory
        """
        self.profile_path = Path(profile_path)
        self._cookies_cache: list[dict] | None = None
        self._last_check: datetime | None = None

    def is_authenticated(self, force_check: bool = False) -> bool:
        """Check if profile has valid Microsoft authentication.

        Args:
            force_check: If True, bypass cache and re-check

        Returns:
            True if authenticated, False otherwise
        """
        # Use cache if recent check exists
        if (
            not force_check
            and self._last_check
            and datetime.now() - self._last_check < timedelta(minutes=5)
        ):
            logger.debug("Using cached authentication status")
            return self._cookies_cache is not None and len(self._cookies_cache) > 0

        try:
            ms_cookies = self._get_ms_cookies()
            self._cookies_cache = ms_cookies
            self._last_check = datetime.now()

            is_auth = len(ms_cookies) >= self.MIN_AUTH_COOKIES
            logger.info(
                f"Profile {self.profile_path.name}: {'Authenticated' if is_auth else 'Not authenticated'} "
                f"({len(ms_cookies)} MS cookies found)"
            )
            return is_auth

        except Exception as e:
            logger.error(f"Error checking authentication: {e}")
            return False

    def _get_ms_cookies(self) -> list[dict]:
        """Extract Microsoft authentication cookies from profile.

        Returns:
            List of Microsoft authentication cookies found
        """
        cookies_file = self.profile_path / "Cookies"
        if not cookies_file.exists():
            logger.debug(f"No cookies file found for {self.profile_path.name}")
            return []

        try:
            # Try to read SQLite database
            # Note: This requires the profile to not be in use by Chrome
            # Alternative: Check Local Storage which is more accessible
            return self._check_local_storage()

        except Exception as e:
            logger.warning(f"Could not read cookies file: {e}")
            # Fallback to checking Local Storage
            return self._check_local_storage()

    def _check_local_storage(self) -> list[dict]:
        """Check Local Storage for Microsoft authentication tokens.

        This is a fallback method when cookies file is locked.

        Returns:
            List of Microsoft auth indicators found
        """
        local_storage_dir = self.profile_path / "Local Storage" / "leveldb"
        if not local_storage_dir.exists():
            return []

        ms_indicators = []

        # Look for files containing Microsoft references
        for file in local_storage_dir.iterdir():
            if file.suffix in [".log", ".ldb"]:
                try:
                    content = file.read_bytes()
                    # Check for Microsoft-related strings
                    if b"login.microsoftonline.com" in content or b"live.com" in content:
                        ms_indicators.append({"file": file.name, "type": "local_storage"})
                except Exception:
                    continue

        return ms_indicators

    def get_authentication_details(self) -> dict:
        """Get detailed authentication information.

        Returns:
            Dictionary with authentication details:
            - is_authenticated: bool
            - cookie_count: int
            - last_checked: str (ISO format)
            - profile_path: str
        """
        is_auth = self.is_authenticated()
        return {
            "is_authenticated": is_auth,
            "cookie_count": len(self._cookies_cache) if self._cookies_cache else 0,
            "last_checked": self._last_check.isoformat() if self._last_check else None,
            "profile_path": str(self.profile_path),
        }

    @staticmethod
    def quick_check_profile(profile_name: str, user_data_dir: Path | None = None) -> bool:
        """Quick authentication check without full initialization.

        Args:
            profile_name: Name of Chrome profile
            user_data_dir: Optional custom user data directory

        Returns:
            True if likely authenticated
        """
        if user_data_dir is None:
            from bing_rewards.utils.chrome_finder import get_chrome_user_data_dir

            user_data_dir = get_chrome_user_data_dir()

        profile_path = user_data_dir / profile_name
        checker = SessionChecker(profile_path)
        return checker.is_authenticated()


def check_profiles_authentication(profiles: list[dict]) -> list[dict]:
    """Check authentication status for multiple profiles.

    Args:
        profiles: List of profile dictionaries with 'path' key

    Returns:
        List of profile dictionaries updated with 'is_authenticated' key
    """
    for profile in profiles:
        try:
            profile_path = Path(profile["path"])
            checker = SessionChecker(profile_path)
            profile["is_authenticated"] = checker.is_authenticated()
            logger.info(
                f"Profile '{profile['name']}': "
                f"{'✓ Authenticated' if profile['is_authenticated'] else '✗ Not authenticated'}"
            )
        except Exception as e:
            logger.warning(f"Could not check authentication for {profile['name']}: {e}")
            profile["is_authenticated"] = False

    return profiles
