"""SSE event stream for pushing framework events to the MCP client.

Events are queued and delivered via Server-Sent Events. The MCP client
(Claude Code) subscribes to receive real-time notifications about:
- App completion/failure
- Intervention requests
- Stamina recovery
- Unknown screen detection
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import dataclass, field
from enum import StrEnum


class EventType(StrEnum):
    APP_COMPLETED = "app_completed"
    APP_FAILED = "app_failed"
    INTERVENTION_REQUESTED = "intervention_requested"
    INTERVENTION_TIMEOUT = "intervention_timeout"
    UNKNOWN_SCREEN = "unknown_screen"
    STAMINA_FULL = "stamina_full"
    PLAN_STEP_COMPLETED = "plan_step_completed"
    PLAN_STEP_FAILED = "plan_step_failed"


@dataclass
class Event:
    type: EventType
    data: dict
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        return f"event: {self.type.value}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"


class EventStream:
    """Thread-safe event queue with async SSE delivery.

    Usage:
        stream = EventStream()

        # Producer (any thread): push events
        stream.push(EventType.APP_COMPLETED, {"app_id": "coffee", "status": "success"})

        # Consumer (async): iterate events
        async for event in stream.subscribe():
            yield event.to_sse()
    """

    def __init__(self, max_history: int = 100) -> None:
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._history: list[Event] = []
        self._max_history = max_history
        self._lock = asyncio.Lock()

    def push(self, event_type: EventType, data: dict) -> None:
        """Push an event to all subscribers. Thread-safe."""
        event = Event(type=event_type, data=data)
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]
        for q in self._subscribers:
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(event)

    async def subscribe(self) -> asyncio.Queue[Event]:
        """Create a new subscription queue. Caller should iterate with queue.get()."""
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=50)
        async with self._lock:
            self._subscribers.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        async with self._lock:
            self._subscribers.remove(q)

    def get_recent_events(self, n: int = 20) -> list[Event]:
        """Get recent events from history."""
        return self._history[-n:]
