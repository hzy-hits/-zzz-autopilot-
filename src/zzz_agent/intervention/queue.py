"""Intervention request queue.

When an automation app encounters a situation it can't handle (unknown screen,
exhausted retries), it creates an intervention request. The Agent must resolve
it before the app can continue.

The queue bridges the framework's sync thread with the MCP server's async world.

TODO(codex): Full implementation. Acceptance criteria:
  - Thread-safe: framework threads push requests, async MCP tools read them
  - Timeout support: requests auto-resolve after configurable timeout
  - SSE notification: push event when new intervention arrives
  - Resolution: resolve() unblocks the waiting framework thread
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


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
        elapsed = time.time() - self.created_at
        return max(0, self.timeout_seconds - elapsed)

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
    """Thread-safe queue for intervention requests.

    Framework threads call request() to create an intervention and block
    until the Agent resolves it or timeout expires.

    MCP tools call list_pending() and resolve() from async context.

    Args:
        default_timeout: Default timeout in seconds for new requests.
    """

    def __init__(self, default_timeout: float = 60.0) -> None:
        self._default_timeout = default_timeout
        self._pending: dict[str, InterventionRequest] = {}
        self._lock = threading.Lock()
        self._counter = 0

    def request(
        self,
        reason: str,
        node_name: str | None = None,
        screenshot_base64: str | None = None,
        options: list[str] | None = None,
        timeout: float | None = None,
    ) -> str:
        """Create an intervention request and block until resolved or timed out.

        Called from framework threads (sync). Blocks the calling thread.

        Args:
            reason: Why intervention is needed (e.g. "SCREEN_UNKNOWN").
            node_name: The Operation node that triggered this.
            screenshot_base64: Screenshot at trigger time.
            options: Available choices (if applicable).
            timeout: Override default timeout.

        Returns:
            The resolution string from the Agent, or "timeout" if timed out.
        """
        with self._lock:
            self._counter += 1
            req_id = f"int_{self._counter:04d}"
            req = InterventionRequest(
                id=req_id,
                reason=reason,
                node_name=node_name,
                screenshot_base64=screenshot_base64,
                options=options or [],
                timeout_seconds=timeout or self._default_timeout,
            )
            self._pending[req_id] = req

        # Block until resolved or timeout
        req._event.wait(timeout=req.timeout_seconds)

        with self._lock:
            if not req.resolved:
                req.resolved = True
                req.resolution = "timeout"
            self._pending.pop(req_id, None)

        return req.resolution

    def list_pending(self) -> list[InterventionRequest]:
        """List all pending (unresolved) intervention requests."""
        with self._lock:
            # Clean up timed-out requests
            timed_out = [k for k, v in self._pending.items() if v.is_timed_out]
            for k in timed_out:
                req = self._pending.pop(k)
                req.resolved = True
                req.resolution = "timeout"
                req._event.set()
            return [v for v in self._pending.values() if not v.resolved]

    def resolve(self, intervention_id: str, action: str) -> bool:
        """Resolve a pending intervention, unblocking the framework thread.

        Args:
            intervention_id: ID of the intervention to resolve.
            action: What the Agent decided to do.

        Returns:
            True if the intervention was found and resolved.
        """
        with self._lock:
            req = self._pending.get(intervention_id)
            if req is None or req.resolved:
                return False
            req.resolved = True
            req.resolution = action
            req._event.set()
            return True
