# SPDX-FileCopyrightText: 2020 jack-mil
#
# SPDX-License-Identifier: MIT

"""Resource monitoring for CPU and memory management."""

import logging
import os
from dataclasses import dataclass
from typing import TypedDict

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(
        "psutil not installed. Resource monitoring disabled. "
        "Install with: pip install psutil"
    )


class ResourceStats(TypedDict):
    """Type definition for resource statistics."""

    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    process_count: int


@dataclass
class ResourceLimits:
    """Resource limits for throttling.

    Attributes:
        cpu_threshold: CPU usage percentage threshold (default 80%)
        memory_threshold: Memory usage percentage threshold (default 85%)
        max_processes: Maximum number of browser processes
        eco_mode: If True, use more conservative limits
    """

    cpu_threshold: float = 80.0
    memory_threshold: float = 85.0
    max_processes: int = 10
    eco_mode: bool = False

    def __post_init__(self):
        """Apply eco mode adjustments."""
        if self.eco_mode:
            self.cpu_threshold = min(self.cpu_threshold, 60.0)
            self.memory_threshold = min(self.memory_threshold, 70.0)
            self.max_processes = max(1, self.max_processes - 3)


class ResourceMonitor:
    """Monitors system resources and provides throttling recommendations.

    Tracks CPU usage, memory consumption, and process count to enable
    intelligent resource management during concurrent browser execution.
    """

    def __init__(self, limits: ResourceLimits | None = None):
        """Initialize resource monitor.

        Args:
            limits: Resource limits configuration
        """
        self.limits = limits or ResourceLimits()
        self._last_cpu_times: dict[int, float] = {}

    def get_stats(self) -> ResourceStats:
        """Get current resource statistics.

        Returns:
            ResourceStats dictionary with current metrics
        """
        if not PSUTIL_AVAILABLE:
            return ResourceStats(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_mb=0.0,
                process_count=0,
            )

        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Get memory stats
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_mb = memory.available / (1024 * 1024)

        # Count Chrome processes
        chrome_count = 0
        for proc in psutil.process_iter(["name"]):
            try:
                if "chrome" in proc.info["name"].lower():
                    chrome_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return ResourceStats(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_available_mb=memory_available_mb,
            process_count=chrome_count,
        )

    def is_within_limits(self) -> bool:
        """Check if current resource usage is within limits.

        Returns:
            True if safe to spawn more instances
        """
        stats = self.get_stats()

        cpu_ok = stats["cpu_percent"] < self.limits.cpu_threshold
        memory_ok = stats["memory_percent"] < self.limits.memory_threshold
        process_ok = stats["process_count"] < self.limits.max_processes

        return cpu_ok and memory_ok and process_ok

    def should_throttle(self) -> bool:
        """Check if throttling should be applied.

        Returns:
            True if resource usage exceeds thresholds
        """
        stats = self.get_stats()

        return (
            stats["cpu_percent"] >= self.limits.cpu_threshold
            or stats["memory_percent"] >= self.limits.memory_threshold
        )

    def get_throttle_recommendation(self) -> dict:
        """Get recommendations for throttling.

        Returns:
            Dictionary with throttle recommendations
        """
        stats = self.get_stats()
        recommendation = {
            "throttle": False,
            "reason": "",
            "suggested_delay": 0.0,
            "max_new_instances": 0,
        }

        if stats["cpu_percent"] >= self.limits.cpu_threshold:
            recommendation["throttle"] = True
            recommendation["reason"] = f"CPU usage high: {stats['cpu_percent']:.1f}%"
            # Calculate delay based on how much we're over threshold
            overage = (
                stats["cpu_percent"] - self.limits.cpu_threshold
            ) / self.limits.cpu_threshold
            recommendation["suggested_delay"] = min(5.0, overage * 2.0)

        if stats["memory_percent"] >= self.limits.memory_threshold:
            recommendation["throttle"] = True
            recommendation[
                "reason"
            ] = f"Memory usage high: {stats['memory_percent']:.1f}%"
            recommendation["suggested_delay"] = max(
                recommendation["suggested_delay"], 3.0
            )

        if stats["process_count"] >= self.limits.max_processes:
            recommendation["throttle"] = True
            recommendation[
                "reason"
            ] = f"Max processes reached: {stats['process_count']}"
            recommendation["max_new_instances"] = 0
        else:
            recommendation["max_new_instances"] = (
                self.limits.max_processes - stats["process_count"]
            )

        return recommendation

    def wait_for_resources(
        self, timeout: float = 30.0, check_interval: float = 1.0
    ) -> bool:
        """Wait until resources are within limits.

        Args:
            timeout: Maximum time to wait (seconds)
            check_interval: How often to check (seconds)

        Returns:
            True if resources became available, False if timeout
        """
        import time

        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.is_within_limits():
                return True
            time.sleep(check_interval)

        return False

    def print_stats(self) -> None:
        """Print current resource statistics."""
        stats = self.get_stats()
        print("\n=== Resource Usage ===")
        print(f"CPU: {stats['cpu_percent']:.1f}%")
        print(f"Memory: {stats['memory_percent']:.1f}%")
        print(f"Available Memory: {stats['memory_available_mb']:.0f} MB")
        print(f"Chrome Processes: {stats['process_count']}")

        if not self.is_within_limits():
            print("⚠️  WARNING: Resource limits exceeded!")
            rec = self.get_throttle_recommendation()
            print(f"   Reason: {rec['reason']}")
        print("=====================\n")
