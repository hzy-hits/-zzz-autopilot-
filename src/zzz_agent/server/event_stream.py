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
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum


class EventType(StrEnum):
    APP_STARTED = "app_started"
    APP_STOPPED = "app_stopped"
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
        self._subscribers: list[tuple[asyncio.Queue[Event], asyncio.AbstractEventLoop]] = []
        self._history: list[Event] = []
        self._max_history = max_history
        self._lock = threading.RLock()

    @staticmethod
    def _push_to_queue(q: asyncio.Queue[Event], event: Event) -> None:
        with contextlib.suppress(asyncio.QueueFull):
            q.put_nowait(event)

    def push(self, event_type: EventType, data: dict) -> None:
        """Push an event to all subscribers from any thread."""
        event = Event(type=event_type, data=data)
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history :]
            subscribers = list(self._subscribers)

        for q, loop in subscribers:
            if loop.is_closed():
                continue
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(self._push_to_queue, q, event)

    async def subscribe(self) -> asyncio.Queue[Event]:
        """Create a new subscription queue. Caller should iterate with queue.get()."""
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=50)
        loop = asyncio.get_running_loop()
        with self._lock:
            self._subscribers.append((q, loop))
        return q

    async def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        with self._lock:
            self._subscribers = [(item_q, loop) for item_q, loop in self._subscribers if item_q is not q]

    def get_recent_events(self, n: int = 20) -> list[Event]:
        """Get recent events from history."""
        with self._lock:
            return list(self._history[-n:])
