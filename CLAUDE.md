# ZZZ-Agent Development Guide

## Project Overview

MCP Server that exposes ZenlessZoneZero-OneDragon framework capabilities as AI-callable tools.
The original framework is imported via PYTHONPATH — zero modifications to its source.

## Architecture

- `src/zzz_agent/server/` — MCP Server + SSE event stream
- `src/zzz_agent/tools/` — MCP tool definitions (thin wrappers calling services)
- `src/zzz_agent/knowledge/` — Three-layer game knowledge service
- `src/zzz_agent/goals/` — Player goal management (YAML persistence)
- `src/zzz_agent/planning/` — Execution plan management (YAML persistence)
- `src/zzz_agent/intervention/` — Intervention queue + monkey-patch
- `src/zzz_agent/state/` — Screenshot → structured game state extraction
- `config/` — Knowledge YAML, goals, agent config

## Running

```bash
# On Windows (where the game runs):
# Set PYTHONPATH to include the original framework
set PYTHONPATH=C:\path\to\ZenlessZoneZero-OneDragon\src
python -m zzz_agent.main --port 8399

# Claude Code in WSL connects via:
# MCP server URL: http://localhost:8399/sse
```

## Code Standards

- Python 3.11, formatted with `ruff format`, linted with `ruff check`
- Type hints on all public functions
- Pydantic models for all MCP tool inputs/outputs
- Async tools use `asyncio.to_thread()` to bridge sync framework calls
- Services are injected via `AgentContext` singleton (see `server/context.py`)

## Testing

```bash
uv run pytest
uv run ruff check src/
uv run ruff format --check src/
```

## Key Dependency

The original framework (`one_dragon.*`, `zzz_od.*`) is NOT a pip dependency.
It's available at runtime via PYTHONPATH. All framework imports must be:
1. Guarded with try/except for dev environments without the framework
2. Lazy-imported (not at module level) where possible
