"""Task planning MCP tools."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from zzz_agent.server.context import get_agent_ctx


def _error(message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": message}
    payload.update(extra)
    return payload


def _status_label(raw_status: Any) -> str:
    value = getattr(raw_status, "value", raw_status)
    mapping = {
        0: "not_run",
        1: "completed",
        2: "failed",
        3: "running",
        "WAIT": "not_run",
        "SUCCESS": "completed",
        "FAIL": "failed",
        "RUNNING": "running",
    }
    return mapping.get(value, str(value).lower())


def register_tools(mcp: FastMCP) -> None:
    """Register all planning tools on the MCP server."""

    @mcp.tool()
    async def create_execution_plan(goal: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
        """Create a persistent execution plan for a goal."""
        ctx = get_agent_ctx()
        plan = ctx.plans.create_plan(goal=goal, steps=steps)
        return plan.to_dict()

    @mcp.tool()
    async def get_execution_plan() -> dict[str, Any] | None:
        """Get the currently active execution plan."""
        ctx = get_agent_ctx()
        plan = ctx.plans.get_active_plan()
        if plan is None:
            return None
        result = plan.to_dict()
        result["progress_summary"] = plan.progress_summary
        current = plan.current_step
        result["current_step_id"] = current.id if current else None
        return result

    @mcp.tool()
    async def update_execution_plan(step_id: str, status: str, notes: str = "") -> dict[str, Any] | None:
        """Update a step's status in the active plan."""
        ctx = get_agent_ctx()
        plan = ctx.plans.update_step(step_id=step_id, status=status, notes=notes)
        if plan is None:
            return None
        result = plan.to_dict()
        result["progress_summary"] = plan.progress_summary
        return result

    @mcp.tool()
    async def list_available_apps() -> list[dict[str, Any]]:
        """List all registered automation apps with descriptions."""
        ctx = get_agent_ctx()
        z_ctx = getattr(ctx, "z_ctx", None)
        run_context = getattr(z_ctx, "run_context", None) if z_ctx is not None else None
        if z_ctx is None or run_context is None:
            return [{"error": "framework unavailable"}]

        active_instance = getattr(z_ctx, "current_instance_idx", None)
        if active_instance is None:
            active_instance = getattr(getattr(z_ctx, "one_dragon_config", None), "current_active_instance", None)
            active_instance = getattr(active_instance, "idx", 0) if active_instance is not None else 0

        default_group_apps = set(getattr(run_context, "default_group_apps", []) or [])
        app_items = list(getattr(run_context, "_application_factory_map", {}).items())
        result: list[dict[str, Any]] = []

        for app_id, factory in app_items:
            try:
                run_record = await asyncio.to_thread(run_context.get_run_record, app_id, active_instance)
                status = _status_label(
                    getattr(run_record, "run_status_under_now", getattr(run_record, "run_status", 0))
                )
                result.append(
                    {
                        "app_id": app_id,
                        "name": getattr(factory, "app_name", app_id),
                        "description": getattr(factory, "app_name", app_id),
                        "is_done_today": bool(getattr(run_record, "is_done", False)),
                        "status": status,
                        "default_group": bool(getattr(factory, "default_group", False) or app_id in default_group_apps),
                    }
                )
            except Exception as exc:
                result.append(
                    {
                        "app_id": app_id,
                        "name": getattr(factory, "app_name", app_id),
                        "description": getattr(factory, "app_name", app_id),
                        "is_done_today": False,
                        "status": "not_run",
                        "default_group": bool(getattr(factory, "default_group", False) or app_id in default_group_apps),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

        return sorted(result, key=lambda item: (not item["default_group"], item["app_id"]))
