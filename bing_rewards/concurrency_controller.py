# SPDX-FileCopyrightText: 2020 jack-mil
#
# SPDX-License-Identifier: MIT

"""Concurrency controller for managing multiple browser instances."""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterator

from bing_rewards.browser_manager import BrowserInstance, BrowserManager, BrowserState
from bing_rewards.event_bus import EventBus, EventType
from bing_rewards.profile_config import ProfileConfig
from bing_rewards.resource_monitor import ResourceLimits, ResourceMonitor

logger = logging.getLogger(__name__)


@dataclass
class ConcurrencyConfig:
    """Configuration for concurrent execution.

    Attributes:
        max_instances: Maximum number of parallel browser instances
        resource_limits: Resource limits for throttling
        enable_throttling: Whether to enable automatic throttling
        instance_timeout: Timeout per instance in seconds
        shutdown_timeout: Timeout for shutdown in seconds
    """

    max_instances: int = 10
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    enable_throttling: bool = True
    instance_timeout: int = 600  # 10 minutes per instance
    shutdown_timeout: int = 30


@dataclass
class InstanceResult:
    """Result from a browser instance execution.

    Attributes:
        instance_id: ID of the instance
        profile_name: Profile name used
        searches_completed: Number of searches completed
        success: Whether execution was successful
        error_message: Error message if failed
        duration_seconds: Execution duration
    """

    instance_id: str
    profile_name: str
    searches_completed: int
    success: bool = True
    error_message: str | None = None
    duration_seconds: float = 0.0


class ConcurrencyController:
    """Controls concurrent execution of multiple browser instances.

    Manages the lifecycle of parallel browser automation, including:
    - Resource monitoring and throttling
    - Instance spawning and coordination
    - Error handling and recovery
    - Progress tracking and reporting

    Example usage:
        controller = ConcurrencyController(max_instances=10)
        results = controller.run_concurrent_searches(
            profiles=profile_list,
            search_func=search_function,
        )
    """

    def __init__(
        self,
        config: ConcurrencyConfig | None = None,
        event_bus: EventBus | None = None,
    ):
        """Initialize concurrency controller.

        Args:
            config: Concurrency configuration
            event_bus: Event bus for publishing events
        """
        self.config = config or ConcurrencyConfig()
        self.event_bus = event_bus or EventBus()
        self.browser_manager = BrowserManager(event_bus=self.event_bus)
        self.resource_monitor = ResourceMonitor(self.config.resource_limits)
        self._results: list[InstanceResult] = []
        self._active_instances: dict[str, BrowserInstance] = {}
        self._shutdown_requested = False

    def run_concurrent_searches(
        self,
        profiles: list[ProfileConfig],
        words_gen_factory: Callable[[], Iterator[str]],
        search_executor: Callable[[BrowserInstance, Iterator[str]], int],
        options: Any,
    ) -> list[InstanceResult]:
        """Run searches concurrently across multiple profiles.

        Args:
            profiles: List of profiles to execute
            words_gen_factory: Factory function to create word generators
            search_executor: Function to execute searches for an instance
            options: Command-line options with settings

        Returns:
            List of InstanceResult objects
        """
        logger.info(f"Starting concurrent execution with {len(profiles)} profiles")
        self._results = []
        start_time = time.time()

        # Use thread pool for concurrent execution
        with ThreadPoolExecutor(max_workers=self.config.max_instances) as executor:
            futures = []

            for i, profile in enumerate(profiles):
                if self._shutdown_requested:
                    logger.warning("Shutdown requested, stopping instance creation")
                    break

                # Wait for resources if throttling enabled
                if (
                    self.config.enable_throttling
                    and not self.resource_monitor.is_within_limits()
                ):
                    logger.info("Waiting for resources...")
                    rec = self.resource_monitor.get_throttle_recommendation()
                    if rec["throttle"]:
                        time.sleep(rec["suggested_delay"])

                # Create and launch instance
                instance_id = f"instance_{i}_{profile.profile_name}"
                future = executor.submit(
                    self._execute_instance,
                    instance_id,
                    profile,
                    words_gen_factory(),
                    search_executor,
                    options,
                )
                futures.append(future)
                self._active_instances[instance_id] = self.browser_manager.get_instance(
                    instance_id
                )

            # Collect results
            for future in futures:
                try:
                    result = future.result(timeout=self.config.instance_timeout)
                    self._results.append(result)
                except Exception as e:
                    logger.error(f"Instance failed: {e}")
                    self._results.append(
                        InstanceResult(
                            instance_id="unknown",
                            profile_name="unknown",
                            searches_completed=0,
                            success=False,
                            error_message=str(e),
                        )
                    )

        duration = time.time() - start_time
        logger.info(
            f"Concurrent execution completed in {duration:.1f}s "
            f"with {len(self._results)} instances"
        )

        return self._results

    def _execute_instance(
        self,
        instance_id: str,
        profile: ProfileConfig,
        words_gen: Iterator[str],
        search_executor: Callable[[BrowserInstance, Iterator[str]], int],
        options: Any,
    ) -> InstanceResult:
        """Execute a single browser instance.

        Args:
            instance_id: Unique instance identifier
            profile: Profile configuration
            words_gen: Word generator for searches
            search_executor: Search execution function
            options: Command-line options

        Returns:
            InstanceResult with execution details
        """
        start_time = time.time()
        logger.info(f"[{instance_id}] Starting execution for {profile.profile_name}")

        try:
            # Create instance
            instance = self.browser_manager.create_instance(instance_id, profile)

            # Launch browser
            agent = (
                options.mobile_agent
                if hasattr(options, "mobile_only") and options.mobile_only
                else options.desktop_agent
            )

            success = instance.launch(
                browser_path=options.browser_path,
                agent=agent,
                load_delay=options.load_delay,
                dry_run=options.dryrun if hasattr(options, "dryrun") else False,
            )

            if not success:
                raise RuntimeError("Failed to launch browser")

            # Execute searches
            searches_completed = search_executor(instance, words_gen)

            duration = time.time() - start_time

            result = InstanceResult(
                instance_id=instance_id,
                profile_name=profile.profile_name,
                searches_completed=searches_completed,
                success=True,
                duration_seconds=duration,
            )

            logger.info(
                f"[{instance_id}] Completed {searches_completed} searches in {duration:.1f}s"
            )

            # Publish completion event
            self.event_bus.emit(
                EventType.SEARCH_COMPLETED,
                source=instance_id,
                profile_name=profile.profile_name,
                data={"count": searches_completed, "duration": duration},
            )

            return result

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[{instance_id}] Failed: {e}")

            # Publish error event
            self.event_bus.emit(
                EventType.INSTANCE_ERROR,
                source=instance_id,
                profile_name=profile.profile_name,
                data={"error": str(e)},
            )

            return InstanceResult(
                instance_id=instance_id,
                profile_name=profile.profile_name,
                searches_completed=0,
                success=False,
                error_message=str(e),
                duration_seconds=duration,
            )

    def get_results_summary(self) -> dict:
        """Get summary of execution results.

        Returns:
            Dictionary with summary statistics
        """
        total_searches = sum(r.searches_completed for r in self._results)
        successful = sum(1 for r in self._results if r.success)
        failed = len(self._results) - successful

        return {
            "total_instances": len(self._results),
            "successful": successful,
            "failed": failed,
            "total_searches": total_searches,
            "success_rate": (successful / len(self._results) * 100)
            if self._results
            else 0,
            "avg_duration": sum(r.duration_seconds for r in self._results)
            / len(self._results)
            if self._results
            else 0,
        }

    def request_shutdown(self) -> None:
        """Request graceful shutdown."""
        logger.info("Shutdown requested")
        self._shutdown_requested = True

    def shutdown(self) -> None:
        """Shutdown all instances immediately."""
        logger.info("Forcing shutdown of all instances")
        self.browser_manager.shutdown_all()
        self._active_instances.clear()

    def get_active_instances(self) -> list[BrowserInstance]:
        """Get currently active instances.

        Returns:
            List of active BrowserInstance objects
        """
        return list(self._active_instances.values())

    def print_status(self) -> None:
        """Print current status to console."""
        print("\n=== Concurrency Status ===")
        print(f"Active Instances: {len(self._active_instances)}")
        print(f"Completed: {len(self._results)}")

        if self._results:
            summary = self.get_results_summary()
            print(f"Total Searches: {summary['total_searches']}")
            print(
                f"Success Rate: {summary['success_rate']:.1f}% "
                f"({summary['successful']}/{summary['total_instances']})"
            )
            print(f"Avg Duration: {summary['avg_duration']:.1f}s")

        # Resource usage
        if self.config.enable_throttling:
            stats = self.resource_monitor.get_stats()
            print(f"\nCPU: {stats['cpu_percent']:.1f}%")
            print(f"Memory: {stats['memory_percent']:.1f}%")
        print("=========================\n")
