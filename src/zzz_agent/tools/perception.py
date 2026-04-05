"""State perception MCP tools.

The Agent's primary new capability: extracting structured game state
that the automation framework cannot see on its own.

Tools in this module observe game state without modifying it.

TODO(codex): Implement all tool bodies. Each tool should:
  1. Get AgentContext via get_agent_ctx()
  2. Access z_ctx (framework context) for data
  3. Use asyncio.to_thread() for sync framework calls
  4. Return JSON-serializable dicts
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP) -> None:
    """Register all perception tools on the MCP server."""

    @mcp.tool()
    async def get_player_state(category: str) -> dict[str, Any]:
        """Navigate to game panels and extract structured player state via screenshot + OCR.

        This is the Agent's key sensing capability — it reads game UI that the
        automation framework doesn't normally parse.

        Args:
            category: One of:
                - "characters": Navigate to character panel, extract level/ascension/skills
                - "inventory": Navigate to backpack, extract material quantities
                - "stamina": Read current stamina from main UI overlay
                - "equipment": Navigate to equipment panel, extract drive disc info
                - "shop": Navigate to shop, extract available items and refresh status

        Returns:
            Structured dict with extracted data. Shape depends on category.
            Example for "stamina": {"current": 180, "max": 240}
            Example for "characters": [{"name": "Lina", "level": 52, "ascension": 4}]

        TODO(codex): Implement.
        - Use z_ctx.controller.screenshot() to capture screen
        - Use z_ctx.ocr for text extraction
        - For non-stamina categories: navigate_to the relevant panel first
        - Parse OCR text into structured data
        - Return dict (not raw text)
        """
        raise NotImplementedError(f"get_player_state({category}) not yet implemented")

    @mcp.tool()
    async def get_screenshot() -> str:
        """Get current game screenshot as base64-encoded PNG.

        Raw visual inspection for when structured extraction isn't enough.
        The Agent can use its vision capability to analyze the image.

        Returns:
            Base64-encoded PNG image string.

        TODO(codex): Implement.
        - Call z_ctx.controller.screenshot() (returns timestamp, numpy array)
        - Convert numpy array to PNG bytes via cv2.imencode
        - Base64 encode and return
        """
        raise NotImplementedError("get_screenshot not yet implemented")

    @mcp.tool()
    async def get_screen_state() -> dict[str, Any]:
        """Get current screen identification and OCR text.

        Lightweight state check — doesn't navigate, just reads current screen.

        Returns:
            {"screen_name": "main_menu", "ocr_text": "...", "confidence": 0.95}

        TODO(codex): Implement.
        - Use z_ctx.screen_loader.current_screen_name
        - Optionally run OCR on current screenshot for text content
        - Return screen name + text
        """
        raise NotImplementedError("get_screen_state not yet implemented")

    @mcp.tool()
    async def get_daily_summary() -> dict[str, Any]:
        """Get today's task completion summary across all apps.

        Returns:
            {
                "date": "2026-04-05",
                "apps": [
                    {"app_id": "coffee", "name": "Coffee Shop", "status": "completed", "run_time": "10:30"},
                    {"app_id": "hollow_zero", "name": "Hollow Zero", "status": "not_run"},
                    ...
                ],
                "completed_count": 3,
                "total_count": 8
            }

        TODO(codex): Implement.
        - Iterate z_ctx.run_context application factories
        - For each, get_run_record(instance_idx) and check run_status_under_now
        - Map STATUS_WAIT/SUCCESS/FAIL/RUNNING to human-readable strings
        - Return summary dict
        """
        raise NotImplementedError("get_daily_summary not yet implemented")

    @mcp.tool()
    async def get_app_status(app_id: str) -> dict[str, Any]:
        """Get detailed run record for a specific app.

        Args:
            app_id: The application identifier (e.g. "hollow_zero", "coffee").

        Returns:
            {
                "app_id": "hollow_zero",
                "status": "completed",
                "last_run_time": "2026-04-05 10:30:00",
                "run_count_today": 2,
                "is_done": true
            }

        TODO(codex): Implement.
        - Get run record via z_ctx.run_context.get_run_record(app_id, instance_idx)
        - Extract status, timing, and completion info
        """
        raise NotImplementedError(f"get_app_status({app_id}) not yet implemented")

    @mcp.tool()
    async def get_game_info() -> dict[str, Any]:
        """Get basic game information: stamina, player level, server time.

        Combines data from multiple sources for a quick overview.

        Returns:
            {
                "stamina": {"current": 180, "max": 240},
                "server_time": "2026-04-05 14:30:00",
                "game_window_ready": true
            }

        TODO(codex): Implement.
        - Check z_ctx.controller.is_game_window_ready
        - Extract stamina via screenshot + OCR (or delegate to get_player_state)
        - Return combined info dict
        """
        raise NotImplementedError("get_game_info not yet implemented")
