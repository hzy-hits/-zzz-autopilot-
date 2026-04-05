# ZZZ-Agent Development Guide

## Project Overview

Thin MCP bridge that exposes ZenlessZoneZero-OneDragon (一条龙) framework as AI-callable tools.
**Claude 做大脑，一条龙做手脚** — Claude sees the screen, decides what to run, and dispatches framework modules.
The original framework is imported via PYTHONPATH — zero modifications to its source.

> **Current status & roadmap**: see [TODO.md](./TODO.md)
> **Module acceptance criteria**: see [docs/acceptance_criteria.md](./docs/acceptance_criteria.md)

## Architecture

```
Claude Code  ──MCP──▶  zzz-agent  ──PYTHONPATH──▶  OneDragon framework  ──▶  Game
    (brain)            (thin bridge)              (automation modules)
```

Source layout:
- `src/zzz_agent/server/` — FastMCP server, AgentContext, SSE event stream
- `src/zzz_agent/tools/` — MCP tool definitions (thin wrappers calling framework/services)
  - `perception.py` — screenshot, screen state, daily summary, app status
  - `dispatch.py` — start/stop/pause/resume app, switch instance
  - `input.py` — click/drag/key/scroll/navigate/find-and-click
  - `planning.py`, `goals.py`, `knowledge.py`, `analysis.py`
- `src/zzz_agent/state/` — Screenshot → structured game state extraction
- `src/zzz_agent/knowledge/` — Three-layer knowledge (framework / remote / discovered) + RAG over guides
- `src/zzz_agent/goals/` — Player goal CRUD (YAML persistence)
- `src/zzz_agent/planning/` — Execution plan management (YAML persistence)
- `src/zzz_agent/intervention/` — Queue + monkey-patch for AI decision points mid-execution
- `config/` — Knowledge YAML, goals, agent config

## Running

**Production (Windows, where the game runs):**

```powershell
# Auto-detects ZenlessZoneZero-OneDragon sibling folder, uses its venv,
# installs only MCP bridge deps via uv pip.
.\start.ps1                                # default port 8399, SSE transport
.\start.ps1 -FrameworkPath D:\path\to\zzz  # explicit framework path
.\start.ps1 -NoFramework                   # dev mode, project's own venv
```

**Claude Code (WSL) connects via** `.mcp.json`:

```json
{
  "mcpServers": {
    "zzz-agent": {
      "command": "npx",
      "args": ["mcp-remote", "http://<windows-host>:8399/sse",
               "--allow-http", "--transport", "sse-only"]
    }
  }
}
```

**Direct stdio (same machine, no SSE):**

```bash
python -m zzz_agent.main --transport stdio --framework-src /path/to/zzz/src
```

## Code Standards

- Python 3.11, formatted with `ruff format`, linted with `ruff check`
- Type hints on all public functions
- Pydantic models for MCP tool inputs/outputs where structured
- Async tools use `asyncio.to_thread()` to bridge sync framework calls
- Services injected via `AgentContext` singleton (see `server/context.py`)
- **No reimplementation of framework capabilities** — delegate to controller/screen_loader/run_context
- **No module-level framework imports** — all lazy or guarded with try/except

## Testing

```bash
uv run pytest                       # unit tests (goals, planning, knowledge, intervention, event_stream, runtime_guards, state_extractor)
uv run ruff check src/
uv run ruff format --check src/
```

## Key Dependency

The original framework (`one_dragon.*`, `zzz_od.*`) is NOT a pip dependency.
It lives in its own venv (the one-dragon launcher). `start.ps1` runs inside that venv and
`uv pip install`s only the 5 MCP bridge packages (fastapi, uvicorn, mcp[cli], pydantic, pyyaml)
into it. This avoids dependency duplication and version conflicts.

All framework imports must be:
1. Guarded with try/except for dev environments without the framework
2. Lazy-imported (not at module level) where possible

## Framework Initialization

`ZContext.init()` does most setup, but the game-window HWND is bound lazily.
`main.py::init_framework()` must call `controller.init_before_context_run()`
after `ctx.init()` to find the game window and initialize the screenshot method —
without this, screenshots capture the foreground window instead of the game.
