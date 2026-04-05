"""Low-level game input MCP tools.

Fallback tools for direct game control during intervention.
Primary workflow should use app dispatch (start_app/stop_app),
not these. These are for when the Agent needs to manually handle
a situation the automation framework can't.

TODO(codex): Implement all tool bodies. Key patterns:
  - All calls go through z_ctx.controller
  - Use asyncio.to_thread() for sync controller calls
  - Coordinate with input coordinates based on game window resolution
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from zzz_agent.server.context import get_agent_ctx


def register_tools(mcp: FastMCP) -> None:
    """Register all low-level input tools on the MCP server."""

    @mcp.tool()
    async def click(x: int, y: int, press_time: float = 0.0) -> dict[str, Any]:
        """Click a screen position.

        Args:
            x: X coordinate in game window.
            y: Y coordinate in game window.
            press_time: How long to hold the click (seconds, 0 = tap).

        Returns:
            {"clicked": true, "x": 300, "y": 400}

        TODO(codex): Implement.
        - Create Point(x, y)
        - Call z_ctx.controller.click(point, press_time)
        """
        raise NotImplementedError("click not yet implemented")

    @mcp.tool()
    async def tap_key(key: str) -> dict[str, Any]:
        """Tap a keyboard key (press and release).

        Args:
            key: Key name (e.g. "space", "enter", "escape", "w", "a", "s", "d").

        Returns:
            {"tapped": true, "key": "space"}

        TODO(codex): Implement.
        - Map key name to framework's key enum
        - Call z_ctx.controller.btn_tap(key)
        """
        raise NotImplementedError(f"tap_key({key}) not yet implemented")

    @mcp.tool()
    async def press_key(key: str, duration: float = 0.5) -> dict[str, Any]:
        """Press and hold a key for a duration.

        Args:
            key: Key name.
            duration: Hold duration in seconds.

        Returns:
            {"pressed": true, "key": "w", "duration": 0.5}

        TODO(codex): Implement.
        - Call z_ctx.controller.btn_press(key, duration)
        """
        raise NotImplementedError(f"press_key({key}) not yet implemented")

    @mcp.tool()
    async def drag(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> dict[str, Any]:
        """Drag from one position to another.

        Args:
            start_x, start_y: Starting position.
            end_x, end_y: Ending position.
            duration: Drag duration in seconds.

        Returns:
            {"dragged": true}

        TODO(codex): Implement.
        - Create Point(start_x, start_y) and Point(end_x, end_y)
        - Call z_ctx.controller.drag_to(end, start, duration)
        """
        raise NotImplementedError("drag not yet implemented")

    @mcp.tool()
    async def scroll(direction: str, amount: int = 3, x: int | None = None, y: int | None = None) -> dict[str, Any]:
        """Scroll the mouse wheel.

        Args:
            direction: "up" or "down".
            amount: Number of scroll steps.
            x, y: Optional position to scroll at (default: center of window).

        Returns:
            {"scrolled": true, "direction": "down", "amount": 3}

        TODO(codex): Implement.
        - Convert direction to positive/negative amount
        - Create Point if x,y provided
        - Call z_ctx.controller.scroll(amount, point)
        """
        raise NotImplementedError("scroll not yet implemented")

    @mcp.tool()
    async def input_text(text: str) -> dict[str, Any]:
        """Type text into the active input field.

        Args:
            text: Text to type.

        Returns:
            {"typed": true, "text": "..."}

        TODO(codex): Implement.
        - Call z_ctx.controller.input_str(text)
        """
        raise NotImplementedError(f"input_text({text}) not yet implemented")

    @mcp.tool()
    async def navigate_to(screen_name: str) -> dict[str, Any]:
        """Navigate to a named game screen using the framework's screen routing.

        Uses the framework's built-in screen transition graph to find the
        shortest path from the current screen to the target.

        Args:
            screen_name: Target screen identifier from the screen route map.

        Returns:
            {"navigated": true, "from": "main_menu", "to": "character_panel"}

        TODO(codex): Implement.
        - Use z_ctx.screen_loader.screen_route_map for pathfinding
        - Execute navigation steps (clicks/transitions)
        - Verify arrival via screen identification
        """
        raise NotImplementedError(f"navigate_to({screen_name}) not yet implemented")

    @mcp.tool()
    async def find_and_click(screen_name: str, area_name: str) -> dict[str, Any]:
        """Find a screen area by template matching and click it.

        More reliable than raw click(x,y) because it uses the framework's
        template matcher to locate UI elements dynamically.

        Args:
            screen_name: Screen containing the target area.
            area_name: Area name within the screen to find and click.

        Returns:
            {"found": true, "clicked": true, "position": {"x": 300, "y": 400}}

        TODO(codex): Implement.
        - Get ScreenArea from z_ctx.screen_loader.get_area(f"{screen_name}.{area_name}")
        - Use template matching to locate the area in current screenshot
        - Click the center of the matched area
        """
        raise NotImplementedError(f"find_and_click({screen_name}.{area_name}) not yet implemented")

    @mcp.tool()
    async def resolve_intervention(intervention_id: str, action: str) -> dict[str, Any]:
        """Resolve a pending intervention request, allowing the paused app to resume.

        Args:
            intervention_id: ID from get_pending_interventions().
            action: What the Agent decided to do (free-form description or option name).

        Returns:
            {"resolved": true, "id": "int_001"}
        """
        ctx = get_agent_ctx()
        if ctx.interventions is None:
            return {"resolved": False, "reason": "Intervention system not initialized"}
        success = ctx.interventions.resolve(intervention_id, action)
        return {"resolved": success, "id": intervention_id}
