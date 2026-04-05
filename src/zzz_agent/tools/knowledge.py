"""Knowledge query MCP tools.

Tools for querying game mechanics, searching strategy guides,
and managing agent-discovered knowledge.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from zzz_agent.server.context import get_agent_ctx


def register_tools(mcp: FastMCP) -> None:
    """Register all knowledge tools on the MCP server."""

    @mcp.tool()
    async def query_game_knowledge(question: str) -> dict[str, Any]:
        """Query game knowledge across all three layers.

        Searches structured data first (exact match), then discovered knowledge.
        Returns source attribution so the Agent knows how much to trust the answer.

        Args:
            question: Natural language question or keyword (e.g. "stamina recovery rate",
                "Lina upgrade materials", "hollow zero weekly limit").

        Returns:
            {
                "found": true,
                "source": "remote",       # "framework" | "remote" | "discovered" | "none"
                "confidence": "synced",    # "authoritative" | "synced" | "unverified"
                "data": {...}              # The actual knowledge data
            }
        """
        ctx = get_agent_ctx()
        result = ctx.knowledge.query(question)
        return {"found": result.found, "source": result.source, "confidence": result.confidence, "data": result.data}

    @mcp.tool()
    async def search_guide(query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Search strategy guides using RAG vector search.

        Searches markdown documents in the guides/ directory for relevant
        strategy information.

        Args:
            query: Natural language search query.
            top_k: Number of results to return (default 3).

        Returns:
            [
                {
                    "source_file": "hollow_zero_guide.md",
                    "content": "...",
                    "relevance_score": 0.85
                }
            ]

        NOTE: Returns empty list if RAG index is not built.
        """
        try:
            ctx = get_agent_ctx()
        except RuntimeError:
            return []
        knowledge = ctx.knowledge
        if knowledge is None:
            return []
        return knowledge.search_guides(query=query, top_k=top_k)

    @mcp.tool()
    async def update_discovered_knowledge(key: str, value: str) -> dict[str, Any]:
        """Write agent-discovered knowledge.

        All discovered knowledge is automatically tagged as "unverified"
        and yields to framework/remote sources on conflict.

        Use this when the Agent discovers new information during gameplay
        (e.g., new character positions, menu layout changes).

        Args:
            key: Knowledge key (used as filename, e.g. "hollow_zero_agent_selection").
            value: Knowledge content (free-form text).

        Returns:
            {"saved": true, "key": "hollow_zero_agent_selection", "trust_level": "unverified"}
        """
        ctx = get_agent_ctx()
        success = ctx.knowledge.update_discovered(key, value)
        return {"saved": success, "key": key, "trust_level": "unverified"}

    @mcp.tool()
    async def sync_remote_knowledge() -> dict[str, Any]:
        """Pull latest knowledge from remote repository.

        Syncs game data (characters, materials, mechanics) from the
        configured remote source.

        Returns:
            {"status": "success", "updated_files": [...]}
        """
        ctx = get_agent_ctx()
        try:
            result = ctx.knowledge.sync_remote()
            return result
        except NotImplementedError:
            return {"status": "not_implemented", "message": "Remote sync not yet configured"}
