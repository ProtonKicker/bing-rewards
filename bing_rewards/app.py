# SPDX-FileCopyrightText: 2020 jack-mil
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import io
import logging
import os
import random
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Iterator

from pynput import keyboard
from pynput.keyboard import Key

from bing_rewards import options as app_options
from bing_rewards.browser_manager import BrowserInstance, BrowserManager, BrowserState
from bing_rewards.concurrency_controller import (
    ConcurrencyConfig,
    ConcurrencyController,
    InstanceResult,
)
from bing_rewards.event_bus import EventBus, EventType
from bing_rewards.profile_config import ProfileConfig, ProfileManager
from bing_rewards.utils.chrome_finder import list_available_profiles

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def word_generator() -> Iterator[str]:
    """Infinitely generate terms from the word file.

    Starts reading from a random position in the file.
    If end of file is reached, close and restart.
    Handles file operations safely and ensures uniform random distribution.

    Yields:
        str: A random keyword from the file, stripped of whitespace.

    Raises:
        OSError: If there are issues accessing or reading the file.
    """
    word_data = resources.files('bing_rewards').joinpath('data', 'keywords.txt')

    try:
        while True:
            with (
                resources.as_file(word_data) as p,
                p.open(mode='r', encoding='utf-8') as fh,
            ):
                # Get the file size of the Keywords file
                fh.seek(0, io.SEEK_END)
                size = fh.tell()

                if size == 0:
                    raise ValueError('Keywords file is empty')

                # Start at a random position in the stream
                fh.seek(random.randint(0, size - 1), io.SEEK_SET)

                # Read and discard partial line to ensure we start at a clean line boundary
                fh.readline()

                # Read lines until EOF
                for raw_line in fh:
                    stripped_line = raw_line.strip()
                    if stripped_line:  # Skip empty lines
                        yield stripped_line

                # If we hit EOF, seek back to start and continue until we've yielded enough words
                fh.seek(0)
                for raw_line in fh:
                    stripped_line = raw_line.strip()
                    if stripped_line:
                        yield stripped_line
    except OSError as e:
        print(f'Error accessing keywords file: {e}')
        raise
    except Exception as e:
        print(f'Unexpected error in word generation: {e}')
        raise


def browser_cmd(exe: Path, agent: str, profile: str = '') -> list[str]:
    """Validate command to open Google Chrome with user-agent `agent`."""
    exe = Path(exe)
    if exe.is_file() and exe.exists():
        cmd = [str(exe.resolve())]
    elif pth := shutil.which(exe):
        cmd = [str(pth)]
    else:
        print(
            f'Command "{exe}" could not be found.\n'
            'Make sure it is available on PATH, '
            'or use the --exe flag to give an absolute path.'
        )
        sys.exit(1)

    cmd.extend(['--new-window', f'--user-agent="{agent}"'])
    # Switch to non default profile if supplied with valid string
    # NO CHECKING IS DONE if the profile exists
    if profile:
        cmd.extend([f'--profile-directory={profile}'])
    if os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland':
        cmd.append('--ozone-platform=x11')
    return cmd


def open_browser(cmd: list[str]) -> subprocess.Popen:
    """Try to open a browser, and exit if the command cannot be found.

    Returns the subprocess.Popen object to handle the browser process.
    """
    try:
        # Open browser as a subprocess
        # Only if a new window should be opened
        if os.name == 'posix':
            chrome = subprocess.Popen(
                cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, start_new_session=True
            )
        else:
            chrome = subprocess.Popen(cmd)
    except OSError as e:
        print('Unexpected error:', e)
        print(f"Running command: '{' '.join(cmd)}'")
        sys.exit(1)

    print(f'Opening browser [{chrome.pid}]')
    return chrome


def close_browser(chrome: subprocess.Popen | None):
    """Close the browser process if it exists and is still running.

    Args:
        chrome: The subprocess.Popen object representing the browser process, or None.
    """
    if chrome is None:
        return

    if chrome.poll() is not None:  # Check if the process has already terminated
        print(f'Browser [{chrome.pid}] has already terminated.')
        return

    print(f'Closing browser [{chrome.pid}]')
    try:
        if os.name == 'posix':
            os.killpg(chrome.pid, signal.SIGTERM)
            # Optionally wait for process termination to avoid zombies
            chrome.wait(timeout=5)  # Wait for up to 5 seconds
        else:
            subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(chrome.pid)],
                capture_output=True,
                check=True,  # raise exception if taskkill fails
                timeout=5,
            )
    except ProcessLookupError:
        print(f'Browser process [{chrome.pid}] not found (already closed).')
    except subprocess.CalledProcessError as e:
        print(f'Error closing browser [{chrome.pid}]: {e}')
        print(f'Stderr: {e.stderr.decode()}')
    except subprocess.TimeoutExpired:
        print(f'Timeout while closing browser [{chrome.pid}].')
    except Exception as e:
        print(f'Unexpected error while closing browser [{chrome.pid}]: {e}')


def search(count: int, words_gen: Iterator[str], agent: str, options: Namespace):
    """Perform the actual searches in a browser.

    Open a chromium browser window with specified `agent` string, complete `count`
    searches from list `words`, finally terminate browser process on completion.
    """
    chrome = None
    if not options.no_window:
        cmd = browser_cmd(options.browser_path, agent, options.profile)
        if not options.dryrun:
            chrome = open_browser(cmd)

    # Wait for Chrome to load
    time.sleep(options.load_delay)

    # keyboard controller from pynput
    key_controller = keyboard.Controller()

    # Ctrl + E to open address bar with the default search engine
    # Alt + D focuses address bar without using search engine
    key_mod, key = (Key.ctrl, 'e') if options.bing else (Key.alt, 'd')

    for i in range(count):
        # Get a random query from set of words
        query = next(words_gen)

        # If user's default search engine is Bing, type the query to the address bar directly
        # Otherwise, form the bing.com search url
        search_url = query if options.bing else options.search_url + quote_plus(query)

        # Use pynput to trigger keyboard events and type search queries
        if not options.dryrun:
            with key_controller.pressed(key_mod):
                key_controller.press(key)
                key_controller.release(key)

            if options.ime:
                # Incase users use a Windows IME, change the language to English
                # Issue #35
                key_controller.tap(Key.shift)
            time.sleep(0.08)

            # Type the url into the address bar
            # with a 30ms delay between keystrokes
            for char in search_url + '\n':
                key_controller.tap(char)
                time.sleep(0.03)
            key_controller.tap(Key.enter)

        print(f'Search {i + 1}: {query}')

        # Delay to let page load
        match options.search_delay:
            case int(x) | float(x) | [float(x)]:
                delay = x
            case [float(min_s), float(max_s)] | [int(min_s), int(max_s)]:
                delay = random.uniform(min_s, max_s)
            case other:
                # catastrophic failure
                raise ValueError(f'Invalid configuration format: "search_delay": {other!r}')

        time.sleep(delay)

    # Skip killing the window if exit flag set
    if options.no_exit:
        return

    close_browser(chrome)


def execute_searches_for_instance(
    instance: BrowserInstance,
    words_gen: Iterator[str],
    options: Namespace,
    desktop_count: int,
    mobile_count: int,
) -> int:
    """Execute searches for a single browser instance.

    Args:
        instance: BrowserInstance to execute searches on
        words_gen: Word generator iterator
        options: Command-line options
        desktop_count: Number of desktop searches
        mobile_count: Number of mobile searches

    Returns:
        Total number of searches completed
    """
    total_completed = 0

    # Desktop searches
    if not options.mobile:
        print(f'[{instance.instance_id}] Doing {desktop_count} desktop searches')
        completed = instance.execute_searches(
            count=desktop_count,
            words_gen=words_gen,
            base_url=options.search_url,
            search_delay=options.search_delay,
            use_bing=options.bing,
            dry_run=options.dryrun,
            event_bus=None,
        )
        total_completed += completed
        print(f'[{instance.instance_id}] Desktop searches complete: {completed}')

    # Mobile searches
    if not options.desktop:
        print(f'[{instance.instance_id}] Doing {mobile_count} mobile searches')
        # Note: In real implementation, would need to relaunch with mobile agent
        # For now, we'll skip mobile in concurrent mode or implement properly later
        if options.mobile:
            completed = instance.execute_searches(
                count=mobile_count,
                words_gen=words_gen,
                base_url=options.search_url,
                search_delay=options.search_delay,
                use_bing=options.bing,
                dry_run=options.dryrun,
                event_bus=None,
            )
            total_completed += completed
            print(f'[{instance.instance_id}] Mobile searches complete: {completed}')

    return total_completed


def run_concurrent_mode(options: Namespace):
    """Run in concurrent multi-instance mode.

    Args:
        options: Command-line options with concurrency settings
    """
    print("\n=== Starting Concurrent Multi-Instance Mode ===")
    print(f"Max Instances: {options.concurrency.max_instances}")
    print(f"Throttling: {'Enabled' if options.concurrency.enable_throttling else 'Disabled'}")
    print(f"Eco Mode: {'Enabled' if options.concurrency.eco_mode else 'Disabled'}\n")

    # Initialize profile manager
    profile_manager = ProfileManager()
    profiles = []

    # Get profiles from command line or use all available
    if hasattr(options, 'profile') and options.profile:
        for profile_name in options.profile:
            profile = profile_manager.get_profile(profile_name)
            if profile:
                profiles.append(profile)
            else:
                # Create new profile config
                profile = ProfileConfig(profile_name=profile_name)
                profile_manager.add_profile(profile)
                profiles.append(profile)
    else:
        # Use all active profiles
        profiles = profile_manager.get_active_profiles()

    if not profiles:
        print("No profiles found. Please specify profiles with --profile flag.")
        return

    print(f"Running {len(profiles)} profile(s): {[p.profile_name for p in profiles]}")

    # Setup event bus for monitoring
    event_bus = EventBus()

    def on_progress(event):
        """Handle progress updates."""
        data = event.data
        print(f"  [{event.profile_name}] Search {data.get('completed', 0)}/{data.get('total', 0)}")

    event_bus.subscribe(EventType.PROGRESS_UPDATE, on_progress)

    # Create concurrency controller
    controller = ConcurrencyController(
        config=ConcurrencyConfig(
            max_instances=options.concurrency.max_instances,
            enable_throttling=options.concurrency.enable_throttling,
            eco_mode=options.concurrency.eco_mode,
            instance_timeout=options.concurrency.instance_timeout,
        ),
        event_bus=event_bus,
    )

    # Word generator factory (each instance needs its own)
    def words_gen_factory():
        return word_generator()

    # Execute concurrently
    try:
        results = controller.run_concurrent_searches(
            profiles=profiles,
            words_gen_factory=words_gen_factory,
            search_executor=lambda inst, wg: execute_searches_for_instance(
                inst, wg, options, options.desktop_count, options.mobile_count
            ),
            options=options,
        )

        # Print summary
        print("\n=== Execution Summary ===")
        summary = controller.get_results_summary()
        print(f"Total Instances: {summary['total_instances']}")
        print(f"Successful: {summary['successful']}")
        print(f"Failed: {summary['failed']}")
        print(f"Total Searches: {summary['total_searches']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Average Duration: {summary['avg_duration']:.1f}s")
        print("========================\n")

    except KeyboardInterrupt:
        print("\nCTRL-C pressed, requesting shutdown...")
        controller.request_shutdown()
        time.sleep(2)
        controller.shutdown()
    finally:
        controller.shutdown()

    # Open rewards dashboard if requested
    if options.open_rewards and not options.dryrun:
        webbrowser.open_new('https://account.microsoft.com/rewards')


def run_manual_login_mode(options: Namespace):
    """Run in manual login mode - launch browsers for user authentication.

    Args:
        options: Command-line options
    """
    print("\n=== Manual Login Mode ===")
    print("This will launch browsers for you to manually sign in to Microsoft accounts.")
    print("Close the browsers manually after signing in.\n")

    profile_names = options.profile if hasattr(options, 'profile') and options.profile else ['Default']

    for profile_name in profile_names:
        print(f"Launching browser for profile: {profile_name}")

        # Launch browser without automation
        cmd = browser_cmd(options.browser_path, options.desktop_agent, profile_name)
        if not options.dryrun:
            chrome = open_browser(cmd)
            print(f"Browser launched [PID: {chrome.pid}]. Please sign in to your Microsoft account.")
            print("Keep this window open while you sign in. Close it when done.")
            print()

    print("\nAfter signing in to all profiles, run bing-rewards normally to automate searches.")

    # Wait for user to close browsers
    try:
        input("Press Enter to exit...")
    except KeyboardInterrupt:
        print("\nExiting...")


def main():
    """Program entrypoint.

    Supports both legacy sequential mode and new concurrent multi-instance mode.
    """
    options = app_options.get_options()

    # Handle special modes first
    if options.list_profiles:
        list_available_profiles('chrome')
        return

    if options.manual_login:
        run_manual_login_mode(options)
        return

    # Choose execution mode based on flags
    if options.concurrent:
        # New concurrent multi-instance mode
        run_concurrent_mode(options)
    else:
        # Legacy sequential mode (maintain backward compatibility)
        words_gen = word_generator()

        def desktop(profile=''):
            # Complete search with desktop settings
            count = options.count if 'count' in options else options.desktop_count
            print(f'Doing {count} desktop searches using "{profile}"')

            temp_options = options
            temp_options.profile = profile
            search(count, words_gen, options.desktop_agent, temp_options)
            print('Desktop Search complete!\n')

        def mobile(profile=''):
            # Complete search with mobile settings
            count = options.count if 'count' in options else options.mobile_count
            print(f'Doing {count} mobile searches using "{profile}"')

            temp_options = options
            temp_options.profile = profile
            search(count, words_gen, options.mobile_agent, temp_options)
            print('Mobile Search complete!\n')

        def both(profile=''):
            desktop(profile)
            mobile(profile)

        # Execute main method in a separate thread
        if options.desktop:
            target_func = desktop
        elif options.mobile:
            target_func = mobile
        else:
            # If neither mode is specified, complete both modes
            target_func = both

        # Run for each specified profile (defaults to ['Default'])
        for profile in options.profile:
            # Start the searching in separate thread
            search_thread = threading.Thread(target=target_func, args=(profile,), daemon=True)
            search_thread.start()

            print('Press ESC to quit searching')

            try:
                # Listen for keyboard events and exit if ESC pressed
                while search_thread.is_alive():
                    with keyboard.Events() as events:
                        event = events.get(timeout=0.5)  # block for 0.5 seconds
                        # Exit if ESC key pressed
                        if event and event.key == Key.esc:
                            print('ESC pressed, terminating')
                            return  # Exit the entire function if ESC is pressed

            except KeyboardInterrupt:
                print('CTRL-C pressed, terminating')
                return  # Exit the entire function if CTRL-C is pressed

            # Wait for the current profile's searches to complete
            search_thread.join()

        # Open rewards dashboard
        if options.open_rewards and not options.dryrun:
            webbrowser.open_new('https://account.microsoft.com/rewards')
