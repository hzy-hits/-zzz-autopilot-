"""Tests for the intervention queue."""

import threading
import time

from zzz_agent.intervention.queue import InterventionQueue


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
