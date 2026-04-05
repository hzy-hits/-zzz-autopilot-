"""Low-level game input MCP tools.

Fallback tools for direct game control during intervention.
Primary workflow should use app dispatch (start_app/stop_app),
not these. These are for when the Agent needs to manually handle
a situation the automation framework can't.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from zzz_agent.server.context import get_agent_ctx
from zzz_agent.tools.navigation import navigate_to_screen

_KEY_ALIASES = {
    "escape": "esc",
    "esc": "esc",
    "return": "enter",
    "enter": "enter",
    "spacebar": "space",
    "space": "space",
    "arrow_up": "up",
    "arrow_down": "down",
    "arrow_left": "left",
    "arrow_right": "right",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "w": "w",
    "a": "a",
    "s": "s",
    "d": "d",
    "tab": "tab",
    "shift": "shift",
    "ctrl": "ctrl",
    "alt": "alt",
    "home": "home",
    "end": "end",
    "pageup": "page_up",
    "pagedown": "page_down",
}


def _framework_error(reason: str) -> dict[str, Any]:
    return {"success": False, "reason": reason}


def _get_ctx():
    ctx = get_agent_ctx()
    if ctx.z_ctx is None:
        return None, _framework_error("framework not available")
    if getattr(ctx.z_ctx, "controller", None) is None:
        return None, _framework_error("game controller not initialized")
    return ctx, None


def _ensure_game_window_ready(ctx: Any) -> dict[str, Any] | None:
    if not getattr(ctx.z_ctx.controller, "is_game_window_ready", False):
        return _framework_error("game window not ready")
    return None


def _normalize_key(key: str) -> str:
    cleaned = key.strip().lower()
    if len(cleaned) == 1:
        return cleaned
    return _KEY_ALIASES.get(cleaned, cleaned)


def _point_from_xy(x: int | None, y: int | None):
    if x is None or y is None:
        return None
    from one_dragon.base.geometry.point import Point

    return Point(x, y)


def _resolve_scroll_point(controller: Any, x: int | None, y: int | None):
    point = _point_from_xy(x, y)
    if point is not None:
        return point

    center_point = getattr(controller, "center_point", None)
    if center_point is None:
        return None
    if hasattr(center_point, "x") and hasattr(center_point, "y"):
        return center_point
    if isinstance(center_point, (tuple, list)) and len(center_point) >= 2:
        return _point_from_xy(int(center_point[0]), int(center_point[1]))
    return None


def register_tools(mcp: FastMCP) -> None:
    """Register all low-level input tools on the MCP server."""

    @mcp.tool()
    async def click(x: int, y: int, press_time: float = 0.0) -> dict[str, Any]:
        """Click a screen position."""
        ctx, error = _get_ctx()
        if error is not None:
            return error
        window_error = _ensure_game_window_ready(ctx)
        if window_error is not None:
            return window_error

        from one_dragon.base.geometry.point import Point

        point = Point(x, y)
        clicked = await asyncio.to_thread(ctx.z_ctx.controller.click, point, press_time)
        if not clicked:
            return {"clicked": False, "x": x, "y": y, "reason": "click failed"}
        return {"clicked": True, "x": x, "y": y, "press_time": press_time}

    @mcp.tool()
    async def tap_key(key: str) -> dict[str, Any]:
        """Tap a keyboard key (press and release)."""
        ctx, error = _get_ctx()
        if error is not None:
            return error
        window_error = _ensure_game_window_ready(ctx)
        if window_error is not None:
            return window_error

        normalized = _normalize_key(key)
        await asyncio.to_thread(ctx.z_ctx.controller.btn_tap, normalized)
        return {"tapped": True, "key": normalized}

    @mcp.tool()
    async def press_key(key: str, duration: float = 0.5) -> dict[str, Any]:
        """Press and hold a key for a duration."""
        ctx, error = _get_ctx()
        if error is not None:
            return error
        window_error = _ensure_game_window_ready(ctx)
        if window_error is not None:
            return window_error

        normalized = _normalize_key(key)
        await asyncio.to_thread(ctx.z_ctx.controller.btn_press, normalized, duration)
        return {"pressed": True, "key": normalized, "duration": duration}

    @mcp.tool()
    async def drag(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> dict[str, Any]:
        """Drag from one position to another."""
        ctx, error = _get_ctx()
        if error is not None:
            return error
        window_error = _ensure_game_window_ready(ctx)
        if window_error is not None:
            return window_error

        from one_dragon.base.geometry.point import Point

        start = Point(start_x, start_y)
        end = Point(end_x, end_y)
        await asyncio.to_thread(ctx.z_ctx.controller.drag_to, start=start, end=end, duration=duration)
        return {
            "dragged": True,
            "start": {"x": start_x, "y": start_y},
            "end": {"x": end_x, "y": end_y},
            "duration": duration,
        }

    @mcp.tool()
    async def scroll(direction: str, amount: int = 3, x: int | None = None, y: int | None = None) -> dict[str, Any]:
        """Scroll the mouse wheel."""
        ctx, error = _get_ctx()
        if error is not None:
            return error
        window_error = _ensure_game_window_ready(ctx)
        if window_error is not None:
            return window_error

        direction_clean = direction.strip().lower()
        if direction_clean not in {"up", "down"}:
            return {"scrolled": False, "reason": f"unsupported direction: {direction}"}

        clicks = amount if direction_clean == "down" else -amount
        point = _resolve_scroll_point(ctx.z_ctx.controller, x, y)
        if point is None:
            return {"scrolled": False, "reason": "scroll target unavailable", "x": x, "y": y}

        await asyncio.to_thread(ctx.z_ctx.controller.scroll, clicks, point)
        return {"scrolled": True, "direction": direction_clean, "amount": amount, "x": x, "y": y}

    @mcp.tool()
    async def input_text(text: str) -> dict[str, Any]:
        """Type text into the active input field."""
        ctx, error = _get_ctx()
        if error is not None:
            return error
        window_error = _ensure_game_window_ready(ctx)
        if window_error is not None:
            return window_error

        await asyncio.to_thread(ctx.z_ctx.controller.input_str, text)
        return {"typed": True, "text": text}

    @mcp.tool()
    async def navigate_to(screen_name: str) -> dict[str, Any]:
        """Navigate to a named game screen using the framework's screen routing."""
        ctx, error = _get_ctx()
        if error is not None:
            return error

        return await navigate_to_screen(ctx.z_ctx, screen_name)

    @mcp.tool()
    async def find_and_click(screen_name: str, area_name: str) -> dict[str, Any]:
        """Find a screen area by template matching and click it."""
        ctx, error = _get_ctx()
        if error is not None:
            return error

        from one_dragon.base.screen import screen_utils

        timestamp, screen = await asyncio.to_thread(ctx.z_ctx.controller.screenshot)
        if screen is None:
            return {
                "found": False,
                "clicked": False,
                "reason": "screenshot unavailable",
                "screen_name": screen_name,
                "area_name": area_name,
            }

        area = await asyncio.to_thread(ctx.z_ctx.screen_loader.get_area, screen_name, area_name)
        if area is None:
            return {
                "found": False,
                "clicked": False,
                "reason": f"area not configured: {screen_name}.{area_name}",
                "screen_name": screen_name,
                "area_name": area_name,
            }

        result = await asyncio.to_thread(screen_utils.find_and_click_area, ctx.z_ctx, screen, screen_name, area_name)
        found = getattr(result, "name", "") not in {"AREA_NO_CONFIG", "OCR_CLICK_NOT_FOUND", "FALSE"}
        clicked = getattr(result, "name", "") in {"OCR_CLICK_SUCCESS", "SUCCESS", "TRUE"}

        if not found:
            return {
                "found": False,
                "clicked": False,
                "reason": f"area not found: {screen_name}.{area_name}",
                "screen_name": screen_name,
                "area_name": area_name,
                "timestamp": timestamp,
            }

        if not clicked:
            return {
                "found": True,
                "clicked": False,
                "reason": f"click failed: {screen_name}.{area_name}",
                "screen_name": screen_name,
                "area_name": area_name,
                "timestamp": timestamp,
            }

        return {
            "found": True,
            "clicked": True,
            "position": {"x": area.center.x, "y": area.center.y},
            "screen_name": screen_name,
            "area_name": area_name,
            "timestamp": timestamp,
        }

    @mcp.tool()
    async def resolve_intervention(intervention_id: str, action: str) -> dict[str, Any]:
        """Resolve a pending intervention request, allowing the paused app to resume."""
        ctx = get_agent_ctx()
        if ctx.interventions is None:
            return {"resolved": False, "reason": "Intervention system not initialized"}
        success = ctx.interventions.resolve(intervention_id, action)
        return {"resolved": success, "id": intervention_id}
