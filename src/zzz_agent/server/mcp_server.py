"""MCP Server definition and tool registration.

Creates a FastMCP instance and registers all tools from the tools/ package.
Tools are thin wrappers that delegate to service objects in AgentContext.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from zzz_agent.tools import analysis, dispatch, goals, input, knowledge, perception, planning


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server with all tools registered."""
    mcp = FastMCP(
        "zzz-agent",
        instructions=(
            "ZZZ-Agent: AI Agent server for ZenlessZoneZero-OneDragon game automation framework.\n\n"
            "You can observe game state, plan task sequences, dispatch automation modules, "
            "intervene at critical decision points, and analyze failures.\n\n"
            "Typical workflow:\n"
            "1. get_goals() + get_daily_summary() -> understand current objectives\n"
            "2. get_player_state('stamina') -> check available resources\n"
            "3. list_available_apps() -> see what modules are available\n"
            "4. create_execution_plan() -> decompose goal into steps\n"
            "5. start_app() for each step -> execute plan\n"
            "6. Monitor via get_app_status() / get_pending_interventions()\n"
            "7. On failure: get_failure_detail() -> analyze and retry"
        ),
    )

    perception.register_tools(mcp)
    planning.register_tools(mcp)
    dispatch.register_tools(mcp)
    analysis.register_tools(mcp)
    input.register_tools(mcp)
    knowledge.register_tools(mcp)
    goals.register_tools(mcp)

    return mcp
