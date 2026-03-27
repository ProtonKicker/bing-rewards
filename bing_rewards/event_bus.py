# SPDX-FileCopyrightText: 2020 jack-mil
#
# SPDX-License-Identifier: MIT

"""Event bus system for GUI preparation and decoupled communication."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events in the system."""

    # Lifecycle events
    INSTANCE_LAUNCHED = auto()
    INSTANCE_TERMINATED = auto()
    INSTANCE_ERROR = auto()
    ALL_COMPLETE = auto()
    SHUTDOWN_STARTED = auto()
    SHUTDOWN_COMPLETE = auto()

    # Search events
    SEARCH_STARTED = auto()
    SEARCH_COMPLETED = auto()
    KEYWORD_TYPED = auto()

    # Progress events
    PROGRESS_UPDATE = auto()
    QUOTA_EXHAUSTED = auto()

    # Authentication events
    AUTH_CHECK_STARTED = auto()
    AUTH_VERIFIED = auto()
    AUTH_FAILED = auto()

    # Resource events
    RESOURCE_LIMIT_REACHED = auto()
    THROTTLING_STARTED = auto()
    THROTTLING_STOPPED = auto()


@dataclass
class Event:
    """Represents an event in the system."""

    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""  # Component that emitted the event
    instance_id: str | None = None  # Browser instance ID if applicable
    profile_name: str | None = None  # Profile name if applicable
    data: dict[str, Any] = field(default_factory=dict)  # Additional event data

    def __str__(self) -> str:
        """String representation of event."""
        return (
            f"Event({self.event_type.name}, "
            f"profile={self.profile_name}, "
            f"data={self.data})"
        )


EventHandler = Callable[[Event], None]


class EventBus:
    """Central event bus for decoupled communication between components.

    This enables future GUI integration by providing a clean API for
    subscribing to and publishing events from any component.

    Example usage:
        bus = EventBus()

        # Subscribe to events
        def on_search_complete(event):
            print(f"Search completed for {event.profile_name}")

        bus.subscribe(EventType.SEARCH_COMPLETED, on_search_complete)

        # Publish event
        bus.publish(Event.SEARCH_COMPLETED, profile_name="Profile 1")
    """

    def __init__(self):
        """Initialize the event bus."""
        self._subscribers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._event_history: list[Event] = []
        self._max_history = 100  # Keep last 100 events

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to an event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Callback function to invoke when event occurs
        """
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler to {event_type.name}")

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe from an event type.

        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler to remove
        """
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            logger.debug(f"Unsubscribed handler from {event_type.name}")

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers.

        Args:
            event: Event object to publish
        """
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # Notify subscribers
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event.event_type.name}: {e}")

        # Log event
        logger.debug(f"Published event: {event}")

    def emit(
        self,
        event_type: EventType,
        source: str = "",
        instance_id: str | None = None,
        profile_name: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> Event:
        """Convenience method to create and publish an event.

        Args:
            event_type: Type of event to emit
            source: Component emitting the event
            instance_id: Browser instance ID if applicable
            profile_name: Profile name if applicable
            data: Additional event data

        Returns:
            The created Event object
        """
        event = Event(
            event_type=event_type,
            source=source,
            instance_id=instance_id,
            profile_name=profile_name,
            data=data or {},
        )
        self.publish(event)
        return event

    def get_history(
        self, event_type: EventType | None = None, limit: int = 10
    ) -> list[Event]:
        """Get recent event history.

        Args:
            event_type: Filter by event type (None for all types)
            limit: Maximum number of events to return

        Returns:
            List of recent events, newest first
        """
        history = self._event_history.copy()
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        return list(reversed(history[-limit:]))

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()

    # Convenience methods for common events
    def on_instance_launched(self, handler: EventHandler) -> None:
        """Subscribe to instance launched events."""
        self.subscribe(EventType.INSTANCE_LAUNCHED, handler)

    def on_instance_terminated(self, handler: EventHandler) -> None:
        """Subscribe to instance terminated events."""
        self.subscribe(EventType.INSTANCE_TERMINATED, handler)

    def on_search_completed(self, handler: EventHandler) -> None:
        """Subscribe to search completed events."""
        self.subscribe(EventType.SEARCH_COMPLETED, handler)

    def on_error(self, handler: EventHandler) -> None:
        """Subscribe to error events."""
        self.subscribe(EventType.INSTANCE_ERROR, handler)

    def on_shutdown(self, handler: EventHandler) -> None:
        """Subscribe to shutdown events."""
        self.subscribe(EventType.SHUTDOWN_STARTED, handler)

    def on_progress_update(self, handler: EventHandler) -> None:
        """Subscribe to progress update events."""
        self.subscribe(EventType.PROGRESS_UPDATE, handler)
