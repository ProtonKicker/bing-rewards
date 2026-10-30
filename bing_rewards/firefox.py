# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Firefox automation: real-profile discovery, per-run clone, driver launch, signed-in gate.

Why Selenium + geckodriver (Marionette) instead of Playwright -juggler:
- Playwright's Firefox build is a special distribution that cannot attach to a
  user profile with real Microsoft login cookies; juggler mode is unstable for
  profile reuse and is not a supported public API.
- geckodriver drives the stock Firefox.app directly and accepts any profile
  directory, so we can clone the logged-in `default-release` profile and keep
  the real one untouched.
"""

from __future__ import annotations

import configparser
import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service

from bing_rewards import options as opts_mod

logger = logging.getLogger(__name__)

FIREFOX_APP = Path('/Applications/Firefox.app/Contents/MacOS/firefox')

# Bing/Microsoft endpoints that must load before we trust a session.
BING_HOME = 'https://www.bing.com/'
REWARDS_HOME = 'https://rewards.bing.com/'


def firefox_profiles_root() -> Path:
    """macOS Firefox application data directory."""
    return Path.home() / 'Library' / 'Application Support' / 'Firefox'


def find_profile_directory(profile_name: str) -> Path:
    """Resolve a Firefox profile *name* (from profiles.ini) to its directory.

    Falls back to the default profile, then to the newest *-release profile.
    """
    root = firefox_profiles_root()
    ini = root / 'profiles.ini'
    if not ini.is_file():
        raise FileNotFoundError(f'Firefox profiles.ini not found at {ini}')

    parser = configparser.ConfigParser()
    parser.read(ini, encoding='utf-8')

    def profile_dirs() -> dict[str, Path]:
        found: dict[str, Path] = {}
        for section in parser.sections():
            if not section.lower().startswith('profile'):
                continue
            path = parser[section].get('Path')
            if not path:
                continue
            directory = (root / path).resolve() if not Path(path).is_absolute() else Path(path)
            found[parser[section].get('Name', directory.name)] = directory
            if parser[section].getboolean('Default', fallback=False):
                found.setdefault('__default__', directory)
        return found

    dirs = profile_dirs()
    if not dirs:
        raise FileNotFoundError(f'no profiles listed in {ini}')
    if profile_name in dirs:
        return dirs[profile_name]
    if '__default__' in dirs:
        logger.warning('profile %r not found; using default profile instead', profile_name)
        return dirs['__default__']
    raise FileNotFoundError(
        f'profile {profile_name!r} not found. Available: '
        f'{", ".join(sorted(k for k in dirs if k != "__default__"))}'
    )


def quit_firefox() -> None:
    """Quit Firefox completely so cookies flush to disk before profile clone."""
    try:
        subprocess.run(
            ['osascript', '-e', 'tell application "Firefox" to quit'],
            capture_output=True,
            timeout=30,
            check=False,
        )
        # Wait for the process to actually exit
        for _ in range(20):
            if not firefox_is_running():
                break
            time.sleep(0.5)
    except Exception as e:  # noqa: BLE001
        logger.warning('error quitting Firefox: %s', e)


def firefox_is_running() -> bool:
    """True if a Firefox process is live; a live browser delays cookie writes."""
    try:
        out = subprocess.run(['pgrep', '-x', 'firefox'], capture_output=True, check=False)
        return out.returncode == 0
    except OSError:
        return False


def clone_profile(source: Path) -> Path:
    """Copy a profile directory to a fresh temp dir and return its path.

    The clone carries login cookies so searches count toward the real account,
    while automation never touches (or can corrupt) the profile in daily use.
    """
    dest = Path(tempfile.mkdtemp(prefix='bing-rewards-profile-'))
    shutil.copytree(source, dest / source.name)
    cloned = dest / source.name
    # Remove a copied lock file; it belongs to the source browser process.
    (cloned / 'lock').unlink(missing_ok=True)
    return cloned


def start_driver(
    profile_dir: Path,
    *,
    mobile_user_agent: str | None = None,
    desktop_user_agent: str | None = None,
    options: opts_mod.Options,
):
    """Launch Firefox against the cloned profile and return a live WebDriver.

    When `mobile_user_agent` is given, Firefox reports as a phone browser via
    the general.useragent.override preference (applies to the whole session).
    Anti-detection measures are applied to avoid Bing Rewards blocking the
    automated session (webdriver flag, automationExtension, etc.).
    """
    ffox = FirefoxOptions()
    binary = options.firefox_binary or (FIREFOX_APP if FIREFOX_APP.exists() else None)
    if binary is not None:
        ffox.binary_location = str(binary)
    ffox.add_argument('-profile')
    ffox.add_argument(str(profile_dir))
    # Silence startup noise that could steal focus or time the run out.
    ffox.set_preference('browser.startup.homepage_override.mstone', 'ignore')
    ffox.set_preference('browser.startup.page', 0)
    ffox.set_preference('datareporting.policy.dataSubmissionEnabled', False)
    ffox.set_preference('app.update.auto', False)
    ffox.set_preference('toolkit.telemetry.reportingpolicy.firstRun', False)
    ffox.set_preference('extensions.getAddons.showPane', False)
    # === Anti-detection: hide automation fingerprints ===
    # Disable the Marionette webdriver flag that Bing uses to reject sessions.
    ffox.set_preference('dom.webdriver.enabled', False)
    ffox.set_preference('useAutomationExtension', False)
    ffox.set_preference('marionette.enabled', False)
    # Suppress the `navigator.webdriver === true` fingerprint.
    ffox.set_preference('dom.webnotifications.enabled', False)
    # Accept-Language header matching the UA locale.
    ffox.set_preference('intl.accept_languages', 'en-US,en;q=0.9')
    # === User-agent override ===
    ua = mobile_user_agent or desktop_user_agent
    if ua:
        ffox.set_preference('general.useragent.override', ua)
    if options.headless:
        ffox.add_argument('--headless')

    service = Service(executable_path=str(options.geckodriver)) if options.geckodriver else Service()
    driver = webdriver.Firefox(service=service, options=ffox)
    driver.set_page_load_timeout(60)
    # Set viewport size: mobile gets a phone viewport, desktop a standard one.
    if mobile_user_agent:
        driver.set_window_size(412, 915)  # Pixel-ish viewport for the mobile card
    else:
        driver.set_window_size(1440, 900)  # Standard desktop viewport
    # Belt-and-suspenders: override navigator.webdriver after page load.
    driver.execute_script(
        'Object.defineProperty(navigator, "webdriver", {get: () => false})'
    )
    return driver


def check_signed_in(driver) -> tuple[bool, str]:
    """Closed-loop gate: verify the session is really logged into Bing.

    Returns (signed_in, reason). Loads bing.com and checks for the account
    avatar or rewards medallion. Cookie presence alone is NOT enough —
    expired auth cookies still exist in the profile but the web session is dead.
    """
    driver.get(BING_HOME)
    # Signed-in: the account anchor points at the profile, not the login page.
    # (is_displayed() is unreliable here — Bing keeps #id_a visually hidden.)
    try:
        anchor = driver.find_element('css selector', '#id_a')
        href = anchor.get_attribute('href') or ''
        if href and 'login' not in href:
            return True, f'account anchor present ({href[:60]})'
    except Exception as e:  # noqa: BLE001 - selenium raises many element-not-found types
        logger.debug('avatar lookup failed: %s', e)

    # Fallback: rewards medallion is a stronger signal — it only renders for
    # authenticated users and carries the live points balance.
    try:
        medallion = driver.find_elements('css selector', '#rh_rwm[data-rewards-widget]')
        if medallion:
            return True, 'rewards medallion present'
    except Exception as e:
        logger.debug('medallion lookup failed: %s', e)

    detail = 'not signed in: no account avatar and no rewards medallion'
    if firefox_is_running():
        detail += (
            ' (note: Firefox was running during profile copy — its newest cookies'
            ' may not be in the clone; quit Firefox and re-run)'
        )
    return False, detail


def quit_driver(driver) -> None:
    try:
        driver.quit()
    except Exception as e:  # noqa: BLE001
        logger.warning('error quitting driver: %s', e)
