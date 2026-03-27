# SPDX-FileCopyrightText: 2020 jack-mil
#
# SPDX-License-Identifier: MIT

"""Browser instance management for concurrent execution."""

from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Iterator

from pynput import keyboard

from bing_rewards.event_bus import EventBus, EventType
from bing_rewards.profile_config import ProfileConfig

logger = logging.getLogger(__name__)


class BrowserState(Enum):
    """State of a browser instance."""

    CREATED = auto()
    LAUNCHING = auto()
    RUNNING = auto()
    SEARCHING = auto()
    COMPLETED = auto()
    ERROR = auto()
    TERMINATED = auto()


@dataclass
class BrowserInstance:
    """Represents a single browser instance for automation.

    Manages the lifecycle of an individual Chromium browser process,
    including launching, executing searches, and cleanup.

    Attributes:
        instance_id: Unique identifier for this instance
        profile: Profile configuration
        state: Current state of the browser
        process: Subprocess.Popen object if running
        search_count: Number of searches completed
    """

    instance_id: str
    profile: ProfileConfig
    state: BrowserState = BrowserState.CREATED
    process: subprocess.Popen | None = None
    search_count: int = 0
    error_message: str | None = None

    def __str__(self) -> str:
        """String representation."""
        return (
            f"BrowserInstance({self.instance_id}, "
            f"profile={self.profile.profile_name}, "
            f"state={self.state.name})"
        )

    def launch(
        self,
        browser_path: str,
        agent: str,
        load_delay: float = 1.5,
        dry_run: bool = False,
    ) -> bool:
        """Launch the browser with specified settings.

        Args:
            browser_path: Path to browser executable
            agent: User agent string to use
            load_delay: Time to wait for browser to load
            dry_run: If True, don't actually launch browser

        Returns:
            True if launch successful, False otherwise
        """
        try:
            self.state = BrowserState.LAUNCHING
            logger.info(f"Launching browser for profile {self.profile.profile_name}")

            if dry_run:
                logger.info("[DRY RUN] Would launch browser")
                self.state = BrowserState.RUNNING
                return True

            # Build command
            cmd = self._build_command(browser_path, agent)

            # Launch browser
            import os

            if os.name == "posix":
                self.process = subprocess.Popen(
                    cmd,
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    start_new_session=True,
                )
            else:
                self.process = subprocess.Popen(cmd)

            logger.info(f"Browser launched [PID: {self.process.pid}]")

            # Wait for browser to load
            time.sleep(load_delay)

            self.state = BrowserState.RUNNING
            return True

        except Exception as e:
            self.state = BrowserState.ERROR
            self.error_message = str(e)
            logger.error(f"Failed to launch browser: {e}")
            return False

    def _build_command(self, browser_path: str, agent: str) -> list[str]:
        """Build the command to launch browser.

        Args:
            browser_path: Path to browser executable
            agent: User agent string

        Returns:
            List of command arguments
        """
        import os
        import shutil

        exe = Path(browser_path)
        if exe.is_file() and exe.exists():
            cmd = [str(exe.resolve())]
        elif pth := shutil.which(exe):
            cmd = [str(pth)]
        else:
            raise FileNotFoundError(
                f'Command "{exe}" could not be found.\n'
                'Make sure it is available on PATH, '
                'or use the --exe flag to give an absolute path.'
            )

        cmd.extend(["--new-window", f'--user-agent="{agent}"'])

        # Handle isolated/temporary profiles
        if self.profile.is_isolated:
            # Create independent Chromium instance
            if self.profile.user_data_dir:
                # Use custom user data directory
                cmd.append(f'--user-data-dir="{self.profile.user_data_dir}"')
            else:
                # Create temporary directory for isolated session
                import tempfile
                temp_dir = Path(tempfile.mkdtemp(prefix=f"bing_rewards_{self.profile.profile_name}_"))
                cmd.append(f'--user-data-dir="{temp_dir}"')
                self.profile.user_data_dir = temp_dir

            # Disable extensions and features for clean isolated session
            cmd.extend([
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-default-apps",
                "--no-first-run",
            ])
        elif self.profile.user_data_dir:
            # Use existing profile directory
            cmd.append(f'--user-data-dir="{self.profile.user_data_dir}"')
        elif self.profile.profile_name:
            # Use named profile from Chrome installation
            cmd.append(f"--profile-directory={self.profile.profile_name}")

        # Wayland compatibility
        if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            cmd.append("--ozone-platform=x11")

        return cmd

    def execute_searches(
        self,
        count: int,
        words_gen: Iterator[str],
        base_url: str,
        search_delay: float | tuple[float, float] = 2.0,
        use_bing: bool = False,
        dry_run: bool = False,
        event_bus: EventBus | None = None,
    ) -> int:
        """Execute searches in the browser.

        Args:
            count: Number of searches to perform
            words_gen: Generator of search keywords
            base_url: Base URL for Bing search
            search_delay: Delay between searches (seconds or range)
            use_bing: If True, Bing is default search engine
            dry_run: If True, don't actually type
            event_bus: Optional event bus for publishing events

        Returns:
            Number of searches completed
        """
        import random
        from urllib.parse import quote_plus

        if self.state != BrowserState.RUNNING:
            logger.warning("Browser not running, cannot execute searches")
            return 0

        self.state = BrowserState.SEARCHING
        completed = 0

        # Keyboard controller
        key_controller = keyboard.Controller()
        key_mod, key = (keyboard.Key.ctrl, "e") if use_bing else (keyboard.Key.alt, "d")

        for i in range(count):
            try:
                # Get keyword
                query = next(words_gen)

                # Build URL
                search_url = query if use_bing else base_url + quote_plus(query)

                # Type the search
                if not dry_run:
                    with key_controller.pressed(key_mod):
                        key_controller.press(key)
                        key_controller.release(key)

                    time.sleep(0.08)

                    # Type URL
                    for char in search_url + "\n":
                        key_controller.tap(char)
                        time.sleep(0.03)
                    key_controller.tap(keyboard.Key.enter)

                print(f"[{self.instance_id}] Search {i + 1}/{count}: {query}")

                # Publish event
                if event_bus:
                    event_bus.emit(
                        EventType.KEYWORD_TYPED,
                        source=self.instance_id,
                        profile_name=self.profile.profile_name,
                        data={"query": query, "search_number": i + 1},
                    )

                # Calculate delay
                match search_delay:
                    case int(x) | float(x) | [float(x)]:
                        delay = x
                    case [float(min_s), float(max_s)] | [int(min_s), int(max_s)]:
                        delay = random.uniform(min_s, max_s)
                    case _:
                        delay = 2.0

                time.sleep(delay)
                completed += 1
                self.search_count = completed

                # Publish progress
                if event_bus:
                    event_bus.emit(
                        EventType.PROGRESS_UPDATE,
                        source=self.instance_id,
                        profile_name=self.profile.profile_name,
                        data={"completed": completed, "total": count},
                    )

            except StopIteration:
                logger.warning("Keyword generator exhausted")
                break
            except Exception as e:
                logger.error(f"Error during search {i + 1}: {e}")
                if event_bus:
                    event_bus.emit(
                        EventType.INSTANCE_ERROR,
                        source=self.instance_id,
                        profile_name=self.profile.profile_name,
                        data={"error": str(e)},
                    )
                break

        self.state = BrowserState.COMPLETED
        return completed

    def close(self, timeout: int = 5) -> None:
        """Close the browser process.

        Args:
            timeout: Timeout for process termination (seconds)
        """
        if self.process is None:
            return

        if self.process.poll() is not None:
            logger.debug(f"Browser [{self.process.pid}] already terminated")
            self.state = BrowserState.TERMINATED
            return

        logger.info(f"Closing browser [{self.process.pid}]")

        try:
            import os

            if os.name == "posix":
                os.killpg(self.process.pid, signal.SIGTERM)
                self.process.wait(timeout=timeout)
            else:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                    capture_output=True,
                    check=True,
                    timeout=timeout,
                )

            self.state = BrowserState.TERMINATED
            logger.info(f"Browser [{self.process.pid}] closed successfully")

        except ProcessLookupError:
            logger.warning(f"Browser process [{self.process.pid}] not found")
            self.state = BrowserState.TERMINATED
        except subprocess.CalledProcessError as e:
            logger.error(f"Error closing browser: {e}")
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout closing browser [{self.process.pid}]")
        except Exception as e:
            logger.error(f"Unexpected error closing browser: {e}")
        finally:
            self.process = None
            self.state = BrowserState.TERMINATED
            # Cleanup temporary user data directory if marked as temporary
            if self.profile.is_temporary and self.profile.user_data_dir:
                self._cleanup_temporary_directory()

    def _cleanup_temporary_directory(self) -> None:
        """Remove temporary user data directory and its contents."""
        import shutil

        if not self.profile.user_data_dir:
            return

        try:
            temp_dir = self.profile.user_data_dir.parent
            if temp_dir.exists() and temp_dir.is_dir():
                logger.info(f"Cleaning up temporary directory: {temp_dir}")
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temporary directory: {e}")

    def is_healthy(self) -> bool:
        """Check if browser process is healthy.

        Returns:
            True if browser is running and responsive
        """
        if self.process is None:
            return False

        # Check if process is still running
        if self.process.poll() is not None:
            return False

        return True

    def get_pid(self) -> int | None:
        """Get the process ID.

        Returns:
            Process ID or None if not running
        """
        return self.process.pid if self.process else None


class BrowserManager:
    """Manages the lifecycle of browser instances.

    Provides methods to create, launch, and manage multiple browser
    instances for concurrent execution.
    """

    def __init__(self, event_bus: EventBus | None = None):
        """Initialize browser manager.

        Args:
            event_bus: Optional event bus for publishing events
        """
        self.instances: dict[str, BrowserInstance] = {}
        self.event_bus = event_bus or EventBus()

    def create_instance(
        self, instance_id: str, profile: ProfileConfig
    ) -> BrowserInstance:
        """Create a new browser instance.

        Args:
            instance_id: Unique identifier for the instance
            profile: Profile configuration

        Returns:
            Created BrowserInstance
        """
        instance = BrowserInstance(instance_id=instance_id, profile=profile)
        self.instances[instance_id] = instance
        logger.info(f"Created browser instance: {instance}")
        return instance

    def launch_instance(
        self,
        instance_id: str,
        browser_path: str,
        agent: str,
        load_delay: float = 1.5,
        dry_run: bool = False,
    ) -> bool:
        """Launch a browser instance.

        Args:
            instance_id: ID of instance to launch
            browser_path: Path to browser executable
            agent: User agent string
            load_delay: Time to wait for browser to load
            dry_run: If True, don't actually launch

        Returns:
            True if successful
        """
        if instance_id not in self.instances:
            logger.error(f"Instance {instance_id} not found")
            return False

        instance = self.instances[instance_id]
        success = instance.launch(browser_path, agent, load_delay, dry_run)

        if success:
            self.event_bus.emit(
                EventType.INSTANCE_LAUNCHED,
                source="BrowserManager",
                instance_id=instance_id,
                profile_name=instance.profile.profile_name,
            )

        return success

    def get_instance(self, instance_id: str) -> BrowserInstance | None:
        """Get an instance by ID.

        Args:
            instance_id: Instance ID

        Returns:
            BrowserInstance or None
        """
        return self.instances.get(instance_id)

    def remove_instance(self, instance_id: str) -> None:
        """Remove an instance (closes if running).

        Args:
            instance_id: Instance ID to remove
        """
        if instance_id in self.instances:
            instance = self.instances[instance_id]
            if instance.state not in [
                BrowserState.TERMINATED,
                BrowserState.COMPLETED,
            ]:
                instance.close()

            del self.instances[instance_id]
            logger.info(f"Removed instance: {instance_id}")

    def get_all_instances(self) -> list[BrowserInstance]:
        """Get all instances.

        Returns:
            List of all BrowserInstance objects
        """
        return list(self.instances.values())

    def get_running_instances(self) -> list[BrowserInstance]:
        """Get instances that are currently running.

        Returns:
            List of running instances
        """
        return [
            inst
            for inst in self.instances.values()
            if inst.state in [BrowserState.RUNNING, BrowserState.SEARCHING]
        ]

    def shutdown_all(self, timeout: int = 5) -> None:
        """Shutdown all instances.

        Args:
            timeout: Timeout for each close operation
        """
        logger.info("Shutting down all browser instances")
        self.event_bus.emit(EventType.SHUTDOWN_STARTED, source="BrowserManager")

        for instance in self.instances.values():
            if instance.state not in [
                BrowserState.TERMINATED,
                BrowserState.COMPLETED,
            ]:
                instance.close(timeout)

        self.event_bus.emit(EventType.SHUTDOWN_COMPLETE, source="BrowserManager")
        logger.info("All browser instances shut down")
