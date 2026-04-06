"""App dispatch MCP tools."""

from __future__ import annotations

import asyncio
import copy
from typing import Any

from mcp.server.fastmcp import FastMCP

from zzz_agent.server.context import get_agent_ctx
from zzz_agent.server.event_stream import EventType


def _error(message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": message}
    payload.update(extra)
    return payload


def _run_state_value(run_context: Any) -> str:
    return str(getattr(run_context, "_run_state", "")).split(".")[-1]


def _current_group_id(ctx: Any) -> str:
    run_context = getattr(ctx, "run_context", None)
    group_id = getattr(run_context, "current_group_id", None)
    return group_id or "one_dragon"


def _resolve_instance_idx(z_ctx: Any, requested: int | None) -> int:
    if requested is not None:
        return int(requested)

    current_instance_idx = getattr(z_ctx, "current_instance_idx", None)
    if current_instance_idx is not None:
        return int(current_instance_idx)

    one_dragon_config = getattr(z_ctx, "one_dragon_config", None)
    current_active_instance = getattr(one_dragon_config, "current_active_instance", None)
    if current_active_instance is not None and getattr(current_active_instance, "idx", None) is not None:
        return int(current_active_instance.idx)

    return 0


async def _ensure_ready_for_application(
    z_ctx: Any, timeout: float = 5.0, poll_interval: float = 0.2
) -> tuple[bool, str | None]:
    if not hasattr(z_ctx, "ready_for_application"):
        return True, None
    if getattr(z_ctx, "ready_for_application", False):
        return True, None

    init_for_application = getattr(z_ctx, "init_for_application", None)
    if init_for_application is None:
        return False, "framework not ready for application dispatch"

    deadline = asyncio.get_running_loop().time() + timeout
    last_error: str | None = None

    while asyncio.get_running_loop().time() < deadline:
        try:
            await asyncio.to_thread(init_for_application)
        except Exception as exc:  # pragma: no cover - framework-only failure path
            last_error = f"{type(exc).__name__}: {exc}"

        if getattr(z_ctx, "ready_for_application", False):
            return True, None

        await asyncio.sleep(poll_interval)

    reason = "framework not ready for application dispatch"
    if last_error is not None:
        reason = f"{reason}: {last_error}"
    return False, reason


def _deep_update(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_update(dict(base[key]), value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def _push_lifecycle_event(ctx: Any, event_name: str, app_id: str, instance_idx: int, state: str) -> str:
    events = getattr(ctx, "events", None)
    if events is None:
        return "events_unavailable"

    if event_name == "started" and hasattr(EventType, "APP_STARTED"):
        events.push(
            EventType.APP_STARTED,
            {"event": "app_started", "app_id": app_id, "instance_idx": instance_idx, "state": state},
        )
        return "APP_STARTED"
    if event_name == "stopped" and hasattr(EventType, "APP_STOPPED"):
        events.push(
            EventType.APP_STOPPED,
            {"event": "app_stopped", "app_id": app_id, "instance_idx": instance_idx, "state": state},
        )
        return "APP_STOPPED"

    # Fallback: reuse existing event kinds because the enum does not expose app lifecycle events.
    fallback = EventType.PLAN_STEP_COMPLETED if event_name == "started" else EventType.APP_COMPLETED
    events.push(
        fallback,
        {
            "event": f"app_{event_name}",
            "app_id": app_id,
            "instance_idx": instance_idx,
            "state": state,
            "note": "fallback event type used because APP_STARTED/APP_STOPPED is unavailable",
        },
    )
    return fallback.value


def register_tools(mcp: FastMCP) -> None:
    """Register all dispatch tools on the MCP server."""

    @mcp.tool()
    async def start_app(
        app_id: str, config: dict[str, Any] | None = None, instance_idx: int | None = None
    ) -> dict[str, Any]:
        """Start an automation app asynchronously."""
        ctx = get_agent_ctx()
        z_ctx = getattr(ctx, "z_ctx", None)
        run_context = getattr(z_ctx, "run_context", None) if z_ctx is not None else None
        if z_ctx is None or run_context is None:
            return _error("framework unavailable", app_id=app_id)

        if _run_state_value(run_context) != "STOP":
            return {"started": False, "reason": "another app is running"}

        ready, ready_error = await _ensure_ready_for_application(z_ctx)
        if not ready:
            return {"started": False, "reason": ready_error or "framework not ready for application dispatch"}

        if not await asyncio.to_thread(run_context.is_app_registered, app_id):
            return {"started": False, "reason": f"app {app_id} is not registered"}

        group_id = _current_group_id(z_ctx)
        resolved_instance_idx = _resolve_instance_idx(z_ctx, instance_idx)

        if config:
            try:
                app_config = await asyncio.to_thread(run_context.get_config, app_id, resolved_instance_idx, group_id)
                if hasattr(app_config, "data") and isinstance(app_config.data, dict):
                    _deep_update(app_config.data, config)
                    await asyncio.to_thread(app_config.save)
                else:
                    return _error("app config object is not editable", app_id=app_id)
            except Exception as exc:
                return _error(f"failed to apply config for {app_id}", detail=f"{type(exc).__name__}: {exc}")

        started = await asyncio.to_thread(run_context.run_application_async, app_id, resolved_instance_idx, group_id)
        if not started:
            return {"started": False, "reason": "failed to schedule app run"}

        event_type = _push_lifecycle_event(z_ctx, "started", app_id, resolved_instance_idx, "RUNNING")
        return {
            "started": True,
            "app_id": app_id,
            "instance_idx": resolved_instance_idx,
            "group_id": group_id,
            "event_type": event_type,
        }

    @mcp.tool()
    async def stop_app() -> dict[str, Any]:
        """Stop the currently running app."""
        ctx = get_agent_ctx()
        z_ctx = getattr(ctx, "z_ctx", None)
        run_context = getattr(z_ctx, "run_context", None) if z_ctx is not None else None
        if z_ctx is None or run_context is None:
            return _error("framework unavailable")

        state = _run_state_value(run_context)
        if state == "STOP":
            return {"stopped": False, "reason": "no app running"}

        await asyncio.to_thread(run_context.stop_running)
        event_type = _push_lifecycle_event(
            z_ctx,
            "stopped",
            getattr(run_context, "current_app_id", "") or "",
            getattr(run_context, "current_instance_idx", 0) or 0,
            "STOP",
        )
        return {"stopped": True, "event_type": event_type}

    @mcp.tool()
    async def pause_app() -> dict[str, Any]:
        """Pause the currently running app."""
        ctx = get_agent_ctx()
        z_ctx = getattr(ctx, "z_ctx", None)
        run_context = getattr(z_ctx, "run_context", None) if z_ctx is not None else None
        if z_ctx is None or run_context is None:
            return _error("framework unavailable")

        if _run_state_value(run_context) != "RUNNING":
            return {"paused": False, "reason": "app is not running"}

        await asyncio.to_thread(run_context.switch_context_pause_and_run)
        return {"paused": True}

    @mcp.tool()
    async def resume_app() -> dict[str, Any]:
        """Resume a paused app."""
        ctx = get_agent_ctx()
        z_ctx = getattr(ctx, "z_ctx", None)
        run_context = getattr(z_ctx, "run_context", None) if z_ctx is not None else None
        if z_ctx is None or run_context is None:
            return _error("framework unavailable")

        if _run_state_value(run_context) != "PAUSE":
            return {"resumed": False, "reason": "app is not paused"}

        await asyncio.to_thread(run_context.switch_context_pause_and_run)
        return {"resumed": True}

    @mcp.tool()
    async def retry_app(app_id: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Stop current app (if running), apply new config, and restart."""
        ctx = get_agent_ctx()
        z_ctx = getattr(ctx, "z_ctx", None)
        run_context = getattr(z_ctx, "run_context", None) if z_ctx is not None else None
        if z_ctx is None or run_context is None:
            return _error("framework unavailable", app_id=app_id)

        if _run_state_value(run_context) != "STOP":
            await stop_app()
            await asyncio.sleep(0.2)
        return await start_app(
            app_id=app_id,
            config=config,
            instance_idx=_resolve_instance_idx(z_ctx, getattr(run_context, "current_instance_idx", None)),
        )

    @mcp.tool()
    async def switch_instance(instance_idx: int) -> dict[str, Any]:
        """Switch to a different game account/instance."""
        ctx = get_agent_ctx()
        z_ctx = getattr(ctx, "z_ctx", None)
        if z_ctx is None or not hasattr(z_ctx, "switch_instance"):
            return _error("framework unavailable", instance_idx=instance_idx)

        await asyncio.to_thread(z_ctx.switch_instance, instance_idx)
        init_for_application = getattr(z_ctx, "init_for_application", None)
        init_error = None
        if init_for_application is not None:
            try:
                await asyncio.to_thread(init_for_application)
            except Exception as exc:  # pragma: no cover - framework-only failure path
                init_error = f"{type(exc).__name__}: {exc}"

        payload = {
            "switched": True,
            "instance_idx": instance_idx,
            "ready_for_application": getattr(z_ctx, "ready_for_application", None),
        }
        if init_error is not None:
            payload["warning"] = f"post-switch init failed: {init_error}"
        return payload

    @mcp.tool()
    async def list_instances() -> list[dict[str, Any]]:
        """List all configured game account instances."""
        ctx = get_agent_ctx()
        z_ctx = getattr(ctx, "z_ctx", None)
        one_dragon_config = getattr(z_ctx, "one_dragon_config", None) if z_ctx is not None else None
        if z_ctx is None or one_dragon_config is None:
            return [{"error": "framework unavailable"}]

        active_idx = getattr(one_dragon_config.current_active_instance, "idx", None)
        instances: list[dict[str, Any]] = []
        for instance in getattr(one_dragon_config, "instance_list", []):
            instances.append(
                {
                    "idx": getattr(instance, "idx", None),
                    "name": getattr(instance, "name", ""),
                    "active": bool(getattr(instance, "idx", None) == active_idx),
                }
            )
        return sorted(instances, key=lambda item: item["idx"] if item["idx"] is not None else -1)
