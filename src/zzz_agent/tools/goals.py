"""Goal management MCP tools.

CRUD operations for player goals. Goals persist in config/goals.yml
and guide the Agent's high-level decision making.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from zzz_agent.server.context import get_agent_ctx


def register_tools(mcp: FastMCP) -> None:
    """Register all goal tools on the MCP server."""

    @mcp.tool()
    async def get_goals() -> list[dict[str, Any]]:
        """Get all player goals, ordered by priority (high first).

        Returns:
            [
                {
                    "id": "goal_abc123",
                    "description": "Level up Lina to 60",
                    "priority": "high",
                    "status": "in_progress",
                    "sub_tasks": ["Collect Ether Core x5 (2/5)", ...],
                    "progress_notes": "...",
                    "created": "2026-04-05"
                }
            ]
        """
        ctx = get_agent_ctx()
        return [g.to_dict() for g in ctx.goals.list_goals()]

    @mcp.tool()
    async def add_goal(
        description: str, priority: str = "medium", sub_tasks: list[str] | None = None
    ) -> dict[str, Any]:
        """Create a new player goal.

        Args:
            description: What the player wants to achieve.
            priority: "high", "medium", or "low".
            sub_tasks: Optional list of sub-task descriptions.

        Returns:
            The created goal dict with generated ID.
        """
        ctx = get_agent_ctx()
        goal = ctx.goals.add_goal(description=description, priority=priority, sub_tasks=sub_tasks)
        return goal.to_dict()

    @mcp.tool()
    async def update_goal(goal_id: str, status: str | None = None, progress_notes: str | None = None) -> dict[str, Any]:
        """Update a goal's status or progress.

        Args:
            goal_id: Goal to update.
            status: New status: "pending", "in_progress", "completed", "abandoned", "recurring".
            progress_notes: Free-form progress update.

        Returns:
            Updated goal dict, or error if not found.
        """
        ctx = get_agent_ctx()
        goal = ctx.goals.update_goal(goal_id=goal_id, status=status, progress_notes=progress_notes)
        if goal is None:
            return {"error": f"Goal {goal_id} not found"}
        return goal.to_dict()

    @mcp.tool()
    async def remove_goal(goal_id: str) -> dict[str, Any]:
        """Delete a goal.

        Args:
            goal_id: Goal to remove.

        Returns:
            {"removed": true} or {"removed": false, "reason": "not found"}.
        """
        ctx = get_agent_ctx()
        success = ctx.goals.remove_goal(goal_id)
        if not success:
            return {"removed": False, "reason": f"Goal {goal_id} not found"}
        return {"removed": True, "goal_id": goal_id}
