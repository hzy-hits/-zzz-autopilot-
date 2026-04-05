"""Tests for event stream thread-safety behavior."""

from __future__ import annotations

import asyncio
import threading

import pytest

from zzz_agent.server.event_stream import EventStream, EventType


@pytest.mark.asyncio
async def test_push_from_sync_thread_reaches_async_subscriber():
    stream = EventStream(max_history=10)
    queue = await stream.subscribe()

    def producer() -> None:
        for i in range(3):
            stream.push(EventType.APP_COMPLETED, {"idx": i})

    thread = threading.Thread(target=producer)
    thread.start()
    thread.join(timeout=2)

    received = []
    for _ in range(3):
        event = await asyncio.wait_for(queue.get(), timeout=1)
        received.append(event.data["idx"])

    assert received == [0, 1, 2]


@pytest.mark.asyncio
async def test_unsubscribe_stops_future_delivery():
    stream = EventStream(max_history=10)
    queue = await stream.subscribe()
    await stream.unsubscribe(queue)

    stream.push(EventType.APP_FAILED, {"msg": "ignored"})
    await asyncio.sleep(0.05)
    assert queue.empty()
