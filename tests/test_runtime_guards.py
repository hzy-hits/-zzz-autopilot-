"""Regression tests for runtime guard behavior around framework integration."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from zzz_agent.intervention.patches import apply_patches
from zzz_agent.tools.dispatch import _ensure_ready_for_application
from zzz_agent.tools.input import _ensure_game_window_ready, _resolve_scroll_point
from zzz_agent.tools.navigation import navigate_to_screen


def _install_screen_modules(
    monkeypatch: pytest.MonkeyPatch, *, matcher=None, click_result_name: str = "SUCCESS"
) -> None:
    one_dragon = types.ModuleType("one_dragon")
    base = types.ModuleType("one_dragon.base")
    screen = types.ModuleType("one_dragon.base.screen")
    screen.screen_utils = SimpleNamespace(
        get_match_screen_name=matcher or (lambda _z_ctx, screen_value: screen_value),
        find_and_click_area=lambda *_args, **_kwargs: SimpleNamespace(name=click_result_name),
    )
    monkeypatch.setitem(sys.modules, "one_dragon", one_dragon)
    monkeypatch.setitem(sys.modules, "one_dragon.base", base)
    monkeypatch.setitem(sys.modules, "one_dragon.base.screen", screen)


def _install_point_module(monkeypatch: pytest.MonkeyPatch) -> None:
    one_dragon = sys.modules.get("one_dragon", types.ModuleType("one_dragon"))
    base = sys.modules.get("one_dragon.base", types.ModuleType("one_dragon.base"))
    geometry = types.ModuleType("one_dragon.base.geometry")
    point = types.ModuleType("one_dragon.base.geometry.point")

    class Point:
        def __init__(self, x: int, y: int) -> None:
            self.x = x
            self.y = y

    point.Point = Point
    monkeypatch.setitem(sys.modules, "one_dragon", one_dragon)
    monkeypatch.setitem(sys.modules, "one_dragon.base", base)
    monkeypatch.setitem(sys.modules, "one_dragon.base.geometry", geometry)
    monkeypatch.setitem(sys.modules, "one_dragon.base.geometry.point", point)


def _install_operation_modules(monkeypatch: pytest.MonkeyPatch, original_notify) -> SimpleNamespace:
    one_dragon = types.ModuleType("one_dragon")
    base = types.ModuleType("one_dragon.base")
    operation = types.ModuleType("one_dragon.base.operation")
    operation_impl = types.ModuleType("one_dragon.base.operation.operation")
    operation_round_result = types.ModuleType("one_dragon.base.operation.operation_round_result")

    operation_notify = SimpleNamespace(send_node_notify=original_notify)

    class OperationRoundResultEnum:
        FAIL = "enum_fail"

    class Operation:
        STATUS_SCREEN_UNKNOWN = "未能识别当前画面"

    operation.operation_notify = operation_notify
    operation_impl.Operation = Operation
    operation_round_result.OperationRoundResultEnum = OperationRoundResultEnum

    monkeypatch.setitem(sys.modules, "one_dragon", one_dragon)
    monkeypatch.setitem(sys.modules, "one_dragon.base", base)
    monkeypatch.setitem(sys.modules, "one_dragon.base.operation", operation)
    monkeypatch.setitem(sys.modules, "one_dragon.base.operation.operation", operation_impl)
    monkeypatch.setitem(sys.modules, "one_dragon.base.operation.operation_round_result", operation_round_result)
    return operation_notify


@pytest.mark.asyncio
async def test_dispatch_waits_for_ready_for_application() -> None:
    z_ctx = SimpleNamespace(ready_for_application=False)

    def init_for_application() -> None:
        z_ctx.ready_for_application = True

    z_ctx.init_for_application = init_for_application

    ready, error = await _ensure_ready_for_application(z_ctx, timeout=0.1, poll_interval=0.0)

    assert ready is True
    assert error is None


@pytest.mark.asyncio
async def test_navigation_rechecks_when_cached_screen_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_screen_modules(monkeypatch, matcher=lambda _z_ctx, screen_value: screen_value)

    screens = iter([(1.0, "ignored"), (2.0, "battlefield")])
    controller = SimpleNamespace(screenshot=lambda: next(screens))

    class ScreenLoader:
        current_screen_name = "menu"

        def update_current_screen_name(self, name: str) -> None:
            self.current_screen_name = name

    result = await navigate_to_screen(SimpleNamespace(controller=controller, screen_loader=ScreenLoader()), "menu")

    assert result["navigated"] is False
    assert result["reason"] == "arrival verification failed"
    assert result["observed"] == "battlefield"


@pytest.mark.asyncio
async def test_navigation_rejects_overlong_route(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_screen_modules(monkeypatch)

    controller = SimpleNamespace(screenshot=lambda: (1.0, "home"))
    route = SimpleNamespace(
        can_go=True,
        from_screen="home",
        node_list=[SimpleNamespace(from_screen="s", from_area="a", to_screen="t")] * 21,
    )

    class ScreenLoader:
        current_screen_name = "home"

        def get_screen_route(self, _current: str, _target: str):
            return route

        def update_current_screen_name(self, _name: str) -> None:
            pass

    result = await navigate_to_screen(SimpleNamespace(controller=controller, screen_loader=ScreenLoader()), "target")

    assert result["navigated"] is False
    assert "route exceeds max steps" in result["reason"]


def test_input_guards_report_unready_window(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_point_module(monkeypatch)

    ctx = SimpleNamespace(z_ctx=SimpleNamespace(controller=SimpleNamespace(is_game_window_ready=False)))
    error = _ensure_game_window_ready(ctx)
    point = _resolve_scroll_point(SimpleNamespace(center_point=(12, 34)), None, None)

    assert error == {"success": False, "reason": "game window not ready"}
    assert point.x == 12
    assert point.y == 34


def test_apply_patches_handles_string_failures_and_runtime_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    original_calls: list[tuple] = []
    operation_notify = _install_operation_modules(monkeypatch, lambda *args: original_calls.append(args))

    requests: list[dict[str, str | None]] = []

    class FakeQueue:
        def set_event_stream(self, _event_stream) -> None:
            pass

        def request(self, *, reason: str, node_name: str | None, screenshot_base64: str | None) -> str:
            requests.append({"reason": reason, "node_name": node_name, "screenshot_base64": screenshot_base64})
            return "continue"

    class FakeRunContext:
        def __init__(self) -> None:
            self._run_state = "RUNNING"
            self.toggle_calls = 0

        def switch_context_pause_and_run(self) -> None:
            self.toggle_calls += 1
            self._run_state = "PAUSE" if self._run_state == "RUNNING" else "RUNNING"

    run_context = FakeRunContext()
    z_ctx = SimpleNamespace(run_context=run_context)

    assert apply_patches(z_ctx, FakeQueue(), object()) is True

    operation = SimpleNamespace(node_retry_times=0, node_max_retry_times=1, last_screenshot=None)
    round_result = SimpleNamespace(result="failed", status="未能识别当前画面", is_fail=True)
    current_node = SimpleNamespace(cn="Node A")

    operation_notify.send_node_notify(operation, round_result, current_node, None)

    assert len(original_calls) == 1
    assert requests == [
        {"reason": "SCREEN_UNKNOWN: 未能识别当前画面", "node_name": "Node A", "screenshot_base64": None}
    ]
    assert run_context.toggle_calls == 2
