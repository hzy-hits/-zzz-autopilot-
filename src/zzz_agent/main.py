"""ZZZ-Agent entry point.

Initializes the framework context, applies patches, starts the MCP server.

Usage:
    # stdio mode (Claude Code spawns as subprocess, recommended):
    python -m zzz_agent.main --transport stdio

    # SSE mode (separate process, connect via HTTP):
    python -m zzz_agent.main --transport sse --port 8399
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger("zzz_agent")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ZZZ-Agent MCP Server")
    parser.add_argument("--port", type=int, default=8399, help="Server port (default: 8399)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument(
        "--framework-src",
        type=str,
        default=None,
        help="Path to ZenlessZoneZero-OneDragon/src (added to PYTHONPATH)",
    )
    parser.add_argument(
        "--config-dir",
        type=str,
        default=None,
        help="Path to zzz-agent config/ directory (default: ./config)",
    )
    parser.add_argument("--no-framework", action="store_true", help="Start without framework (dev/test mode)")
    parser.add_argument(
        "--transport",
        type=str,
        default="stdio",
        choices=["stdio", "sse"],
        help="MCP transport: stdio (Claude Code subprocess) or sse (HTTP server)",
    )
    parser.add_argument("--log-level", type=str, default="INFO", help="Logging level")
    return parser.parse_args()


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def init_framework(framework_src: str | None) -> object | None:
    """Initialize the ZZZ-OneDragon framework context.

    Args:
        framework_src: Path to add to sys.path for framework imports.

    Returns:
        ZContext instance, or None if framework is not available.
    """
    if framework_src:
        sys.path.insert(0, framework_src)
        logger.info(f"Added framework source to path: {framework_src}")

    try:
        from zzz_od.context.zzz_context import ZContext

        ctx = ZContext()
        ctx.init()
        logger.info("Framework ZContext initialized successfully")

        # Initialize controller for screenshot/input (finds game window HWND, sets up screenshot method)
        if ctx.controller is not None:
            ctx.controller.init_before_context_run()
            if ctx.controller.is_game_window_ready:
                logger.info("Game window bound successfully")
            else:
                logger.warning("Game window not found — is the game running?")

        if hasattr(ctx, "ready_for_application") and not ctx.ready_for_application:
            logger.error("Framework initialized but not ready for application dispatch")

        return ctx
    except ImportError as e:
        logger.warning(f"Framework not available: {e}")
        return None
    except Exception as e:
        logger.error(f"Framework initialization failed: {e}")
        return None


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)

    config_dir = Path(args.config_dir) if args.config_dir else Path(__file__).parent.parent.parent / "config"
    config_dir = config_dir.resolve()
    logger.info(f"Config directory: {config_dir}")

    # 1. Initialize framework (optional)
    z_ctx = None
    if not args.no_framework:
        z_ctx = init_framework(args.framework_src)
        if z_ctx is None:
            logger.warning("Running in dev mode without framework. Some tools will not work.")

    # 2. Initialize services
    from zzz_agent.goals.manager import GoalManager
    from zzz_agent.intervention.queue import InterventionQueue
    from zzz_agent.knowledge.service import KnowledgeService
    from zzz_agent.planning.store import PlanStore
    from zzz_agent.server.context import AgentContext, init_agent_ctx
    from zzz_agent.server.event_stream import EventStream

    framework_config_dir = None
    if args.framework_src:
        candidate = Path(args.framework_src).parent / "config"
        if candidate.exists():
            framework_config_dir = candidate

    agent_ctx = AgentContext(
        z_ctx=z_ctx,
        knowledge=KnowledgeService(config_dir=config_dir, framework_config_dir=framework_config_dir),
        goals=GoalManager(goals_file=config_dir / "goals.yml"),
        plans=PlanStore(plans_dir=config_dir / "plans"),
        interventions=InterventionQueue(default_timeout=60.0),
        events=EventStream(),
        config_dir=config_dir,
        framework_src_dir=Path(args.framework_src) if args.framework_src else None,
    )
    init_agent_ctx(agent_ctx)
    logger.info("AgentContext initialized with all services")

    if agent_ctx.interventions is not None:
        agent_ctx.interventions.set_event_stream(agent_ctx.events)

    # 3. Apply monkey-patch (only if framework is available)
    if z_ctx is not None:
        from zzz_agent.intervention.patches import apply_patches

        patched = apply_patches(z_ctx, agent_ctx.interventions, agent_ctx.events)
        if patched:
            logger.info("Framework monkey-patch applied")
        else:
            logger.warning("Monkey-patch skipped")

    # 4. Create and run MCP server
    from zzz_agent.server.mcp_server import create_mcp_server

    mcp = create_mcp_server(host=args.host, port=args.port)
    if args.transport == "stdio":
        logger.info("Starting MCP server with stdio transport")
        mcp.run(transport="stdio")
    else:
        logger.info(f"Starting MCP server on {args.host}:{args.port}")
        mcp.run(transport="sse")


if __name__ == "__main__":
    main()
