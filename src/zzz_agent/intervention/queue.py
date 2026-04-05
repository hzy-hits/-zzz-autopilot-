"""Intervention request queue.

Thread-safe bridge between framework sync threads and MCP async tools.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zzz_agent.server.event_stream import EventStream


@dataclass
class InterventionRequest:
    """A pending intervention request from the automation framework."""

    id: str
    reason: str
    node_name: str | None = None
    screenshot_base64: str | None = None
    options: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    timeout_seconds: float = 60.0
    resolved: bool = False
    resolution: str = ""
    _event: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def timeout_remaining(self) -> float:
        return max(0.0, self.timeout_seconds - (time.time() - self.created_at))

    @property
    def is_timed_out(self) -> bool:
        return self.timeout_remaining <= 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "reason": self.reason,
            "node_name": self.node_name,
            "screenshot_base64": self.screenshot_base64,
            "options": self.options,
            "timeout_remaining_seconds": round(self.timeout_remaining, 1),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.created_at)),
        }


class InterventionQueue:
    """Thread-safe queue for intervention requests."""

    def __init__(self, default_timeout: float = 60.0, event_stream: EventStream | None = None) -> None:
        self._default_timeout = default_timeout
        self._pending: dict[str, InterventionRequest] = {}
        self._lock = threading.Lock()
        self._counter = 0
        self._event_stream = event_stream

    def set_event_stream(self, event_stream: EventStream | None) -> None:
        """Attach or replace queue-level event stream."""
        self._event_stream = event_stream

    def _push_event(self, event_name: str, payload: dict) -> None:
        if self._event_stream is None:
            return
        try:
            from zzz_agent.server.event_stream import EventType

            self._event_stream.push(EventType(event_name), payload)
        except Exception:
            # Queue behavior must not fail because event delivery failed.
            return

    def _expire_request_locked(self, req: InterventionRequest) -> None:
        req.resolved = True
        req.resolution = "timeout"
        req._event.set()
        self._push_event(
            "intervention_timeout",
            {
                "id": req.id,
                "reason": req.reason,
                "node_name": req.node_name,
            },
        )

    def request(
        self,
        reason: str,
        node_name: str | None = None,
        screenshot_base64: str | None = None,
        options: list[str] | None = None,
        timeout: float | None = None,
    ) -> str:
        """Create an intervention request and block until resolved or timed out."""
        with self._lock:
            self._counter += 1
            req_id = f"int_{self._counter:04d}"
            req = InterventionRequest(
                id=req_id,
                reason=reason,
                node_name=node_name,
                screenshot_base64=screenshot_base64,
                options=list(options or []),
                timeout_seconds=float(timeout if timeout is not None else self._default_timeout),
            )
            self._pending[req_id] = req
            self._push_event(
                "intervention_requested",
                {
                    "id": req.id,
                    "reason": req.reason,
                    "node_name": req.node_name,
                    "timeout_seconds": req.timeout_seconds,
                },
            )

        req._event.wait(timeout=req.timeout_seconds)

        with self._lock:
            if not req.resolved:
                self._expire_request_locked(req)
            self._pending.pop(req_id, None)
            return req.resolution

    def list_pending(self) -> list[InterventionRequest]:
        """List all pending unresolved intervention requests."""
        with self._lock:
            timed_out = [req for req in self._pending.values() if not req.resolved and req.is_timed_out]
            for req in timed_out:
                self._expire_request_locked(req)
                self._pending.pop(req.id, None)

            return [req for req in self._pending.values() if not req.resolved]

    def resolve(self, intervention_id: str, action: str) -> bool:
        """Resolve a pending intervention, unblocking the framework thread."""
        with self._lock:
            req = self._pending.get(intervention_id)
            if req is None or req.resolved:
                return False
            req.resolved = True
            req.resolution = action
            req._event.set()
            return True
