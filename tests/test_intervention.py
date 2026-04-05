"""Tests for the intervention queue."""

import threading
import time

from zzz_agent.intervention.queue import InterventionQueue
from zzz_agent.server.event_stream import EventStream, EventType


def test_resolve_unblocks_request():
    queue = InterventionQueue(default_timeout=5.0)
    result = [None]

    def requester():
        result[0] = queue.request(reason="test", node_name="node1")

    t = threading.Thread(target=requester)
    t.start()
    time.sleep(0.1)  # Let the thread block

    pending = queue.list_pending()
    assert len(pending) == 1
    assert pending[0].reason == "test"

    queue.resolve(pending[0].id, "click_button")
    t.join(timeout=2)
    assert result[0] == "click_button"


def test_timeout():
    queue = InterventionQueue(default_timeout=0.3)
    result = [None]

    def requester():
        result[0] = queue.request(reason="timeout_test", timeout=0.3)

    t = threading.Thread(target=requester)
    t.start()
    t.join(timeout=2)
    assert result[0] == "timeout"


def test_list_pending_empty():
    queue = InterventionQueue()
    assert queue.list_pending() == []


def test_resolve_nonexistent():
    queue = InterventionQueue()
    assert queue.resolve("fake_id", "action") is False


def test_list_pending_cleans_timeout():
    queue = InterventionQueue(default_timeout=0.05)
    done = {"value": None}

    def requester():
        done["value"] = queue.request(reason="timeout_cleanup")

    t = threading.Thread(target=requester)
    t.start()
    time.sleep(0.08)
    # Trigger cleanup path.
    pending = queue.list_pending()
    assert pending == []
    t.join(timeout=1)
    assert done["value"] == "timeout"


def test_request_pushes_events():
    stream = EventStream()
    queue = InterventionQueue(default_timeout=0.2, event_stream=stream)
    result = {"value": None}

    def requester():
        result["value"] = queue.request(reason="need_input", node_name="node_x", timeout=0.05)

    t = threading.Thread(target=requester)
    t.start()
    t.join(timeout=1)
    assert result["value"] == "timeout"

    events = stream.get_recent_events(10)
    event_types = [event.type for event in events]
    assert EventType.INTERVENTION_REQUESTED in event_types
    assert EventType.INTERVENTION_TIMEOUT in event_types
