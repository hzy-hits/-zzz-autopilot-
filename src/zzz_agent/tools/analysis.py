"""Failure analysis MCP tools.

Understanding WHY things failed — the framework only records THAT they failed.
These tools provide rich context for the Agent to diagnose issues and adjust strategy.

TODO(codex): Implement all tool bodies. Key data sources:
  - RunRecord for status/timing
  - Operation execution logs (framework logging)
  - Screenshots at failure points
  - InterventionQueue for pending decisions
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from zzz_agent.server.context import get_agent_ctx


def register_tools(mcp: FastMCP) -> None:
    """Register all analysis tools on the MCP server."""

    @mcp.tool()
    async def get_failure_detail(app_id: str) -> dict[str, Any]:
        """Get rich failure context for a failed app run.

        Provides everything the Agent needs to diagnose why an app failed
        and decide whether to retry, adjust config, or escalate.

        Args:
            app_id: The failed app's identifier.

        Returns:
            {
                "app_id": "hollow_zero",
                "status": "failed",
                "last_node": "select_combat_agent",
                "last_node_status": "SCREEN_UNKNOWN",
                "screenshot_base64": "...",  # Screenshot at failure point
                "retry_count": 3,
                "max_retries": 3,
                "error_log": "...",  # Last N log lines
                "duration_seconds": 180,
                "failure_time": "2026-04-05 14:30:00"
            }

        TODO(codex): Implement.
        - Get RunRecord for app_id
        - Read framework's log file for recent entries related to this app
        - If z_ctx has last_screenshot, encode it
        - Extract node name from operation execution state
        - Return combined failure context
        """
        raise NotImplementedError(f"get_failure_detail({app_id}) not yet implemented")

    @mcp.tool()
    async def get_app_execution_log(app_id: str, last_n: int = 50) -> list[dict[str, Any]]:
        """Get recent execution log entries for an app.

        Provides a timeline of what the app did before failing.

        Args:
            app_id: App identifier.
            last_n: Number of recent log lines to return (default 50).

        Returns:
            [
                {"timestamp": "14:30:01", "level": "INFO", "message": "Node started: navigate_to_hollow"},
                {"timestamp": "14:30:15", "level": "WARNING", "message": "Template match failed"},
                {"timestamp": "14:30:16", "level": "ERROR", "message": "Node failed after 3 retries"},
            ]

        TODO(codex): Implement.
        - Read framework's log file (typically in .log/ directory)
        - Filter entries for the given app_id
        - Parse timestamp, level, message
        - Return last_n entries
        """
        raise NotImplementedError(f"get_app_execution_log({app_id}) not yet implemented")

    @mcp.tool()
    async def get_pending_interventions() -> list[dict[str, Any]]:
        """List intervention requests waiting for Agent decision.

        When an automation app encounters an unknown screen or exhausts retries,
        it pauses and creates an intervention request. The Agent must resolve it
        before the app can continue.

        Returns:
            [
                {
                    "id": "int_001",
                    "reason": "SCREEN_UNKNOWN",
                    "node_name": "select_event_option",
                    "screenshot_base64": "...",
                    "options": ["option_1", "option_2", "option_3"],
                    "timeout_remaining_seconds": 45,
                    "created_at": "2026-04-05 14:30:00"
                }
            ]
        """
        ctx = get_agent_ctx()
        if ctx.interventions is None:
            return []
        return [i.to_dict() for i in ctx.interventions.list_pending()]
