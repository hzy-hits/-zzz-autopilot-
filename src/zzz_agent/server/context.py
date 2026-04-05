"""Shared context for all MCP tools and services.

AgentContext holds references to all services and the framework's ZContext.
Tools access it via get_agent_ctx(). Initialized once in main.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zzz_agent.goals.manager import GoalManager
    from zzz_agent.intervention.queue import InterventionQueue
    from zzz_agent.knowledge.service import KnowledgeService
    from zzz_agent.planning.store import PlanStore
    from zzz_agent.server.event_stream import EventStream

_agent_ctx: AgentContext | None = None


@dataclass
class AgentContext:
    """Central context shared by all MCP tools.

    Attributes:
        z_ctx: The original framework's OneDragonContext instance.
            None when running in dev/test mode without the framework.
        knowledge: Three-layer game knowledge query service.
        goals: Player goal CRUD and persistence.
        plans: Execution plan persistence and query.
        interventions: Queue for pending intervention requests.
        events: SSE event stream for push notifications.
        config_dir: Path to config/ directory for YAML persistence.
        framework_src_dir: Path to the original framework's src/ directory.
    """

    z_ctx: object | None = None
    knowledge: KnowledgeService | None = None
    goals: GoalManager | None = None
    plans: PlanStore | None = None
    interventions: InterventionQueue | None = None
    events: EventStream | None = None
    config_dir: Path = field(default_factory=lambda: Path("config"))
    framework_src_dir: Path | None = None


def init_agent_ctx(ctx: AgentContext) -> None:
    global _agent_ctx
    _agent_ctx = ctx


def get_agent_ctx() -> AgentContext:
    if _agent_ctx is None:
        raise RuntimeError("AgentContext not initialized. Call init_agent_ctx() first.")
    return _agent_ctx
