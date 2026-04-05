"""Task planning MCP tools.

The Agent's core strategic capability: decomposing goals into
executable module call chains with preconditions and expected outcomes.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from zzz_agent.server.context import get_agent_ctx


def register_tools(mcp: FastMCP) -> None:
    """Register all planning tools on the MCP server."""

    @mcp.tool()
    async def create_execution_plan(goal: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
        """Create a persistent execution plan for a goal.

        Plans survive Agent disconnection. On reconnect, get_execution_plan()
        returns the plan with step statuses preserved.

        Args:
            goal: High-level goal description (e.g. "Level up Lina to 60").
            steps: Ordered list of steps, each with:
                - app_id (str, required): Which automation module to call
                - config (dict, optional): Config overrides for the app
                - precondition (str, optional): What must be true before this step
                - expected_outcome (str, optional): What success looks like

        Returns:
            The created plan as a dict with id, goal, steps, and status.
        """
        ctx = get_agent_ctx()
        plan = ctx.plans.create_plan(goal=goal, steps=steps)
        return plan.to_dict()

    @mcp.tool()
    async def get_execution_plan() -> dict[str, Any] | None:
        """Get the currently active execution plan.

        Returns:
            Active plan dict with step statuses, or None if no active plan.
            Includes progress_summary field showing "3/5 steps completed".
        """
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
        """Update a step's status in the active plan.

        Args:
            step_id: Step to update (e.g. "step_1").
            status: New status: "pending", "in_progress", "completed", "failed", "skipped".
            notes: Optional notes about the step result or failure reason.

        Returns:
            Updated plan dict, or None if no active plan.
        """
        ctx = get_agent_ctx()
        plan = ctx.plans.update_step(step_id=step_id, status=status, notes=notes)
        if plan is None:
            return None
        result = plan.to_dict()
        result["progress_summary"] = plan.progress_summary
        return result

    @mcp.tool()
    async def list_available_apps() -> list[dict[str, Any]]:
        """List all registered automation apps with descriptions.

        Returns:
            List of app info dicts:
            [
                {
                    "app_id": "hollow_zero",
                    "name": "Hollow Zero",
                    "description": "Auto-run Hollow Zero dungeon",
                    "is_done_today": false,
                    "status": "not_run",
                    "default_group": true
                },
                ...
            ]

        TODO(codex): Implement.
        - Iterate z_ctx.run_context._application_factory_map
        - For each factory: get app_id, app_name, default_group
        - Get run record to check today's status
        - Return list sorted by default_group (default first), then app_id
        """
        raise NotImplementedError("list_available_apps not yet implemented")
