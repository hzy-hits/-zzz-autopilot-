# ZZZ-Agent Development Guide

## Project Overview

MCP bridge that lets Claude orchestrate ZenlessZoneZero-OneDragon (一条龙) at the **App level**.
Claude decides which automation module to run; the framework handles all low-level game interaction
(screenshot, OCR, input, navigation) internally. Zero modifications to framework source.

> **Current status & roadmap**: see [TODO.md](./TODO.md)
> **Module acceptance criteria**: see [docs/acceptance_criteria.md](./docs/acceptance_criteria.md)

## Architecture

```
Claude Code  ──MCP──▶  zzz-agent  ──PYTHONPATH──▶  OneDragon framework  ──▶  Game
   (plan)         (dispatch + monitor)           (screenshot/OCR/input/nav)
```

**Core workflow**: `list_available_apps` → `start_app(id)` → `get_app_status` → `get_failure_detail` / `retry_app`

Source layout:
- `src/zzz_agent/server/` — FastMCP server, AgentContext, SSE event stream
- `src/zzz_agent/tools/` — MCP tool definitions
  - `dispatch.py` — **primary**: start/stop/pause/resume app, switch instance
  - `perception.py` — app status, daily summary, game info (screenshot only works with game in foreground)
  - `analysis.py` — failure detail, execution logs, pending interventions
  - `input.py` — low-level click/key/drag (only usable when game is in foreground, prefer app-level dispatch)
  - `planning.py`, `goals.py`, `knowledge.py`
- `src/zzz_agent/state/` — Screenshot → structured state extraction (used internally by perception tools)
- `src/zzz_agent/knowledge/` — Three-layer knowledge + RAG over guides
- `src/zzz_agent/goals/` — Player goal CRUD (YAML persistence)
- `src/zzz_agent/planning/` — Execution plan management (YAML persistence)
- `src/zzz_agent/intervention/` — Queue + monkey-patch for AI decision points mid-execution
- `config/` — Knowledge YAML, goals, agent config

### Known limitations

- **Screenshot/OCR/input require game in foreground** — the framework's capture methods (PrintWindow/BitBlt)
  don't reliably capture ZZZ's DirectX content in background. Windows also blocks `win.activate()` with
  ACCESS_DENIED due to focus-stealing prevention. Use `start_app` instead of raw input tools.
- **No story progression module** — the framework has daily task apps but no main storyline automation.

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
- **No reimplementation of framework capabilities** — delegate to apps via `start_app`, not raw input
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

`ZContext.init()` does most setup. `main.py::init_framework()` then calls
`controller.init_before_context_run()` to bind the game window HWND and
initialize the screenshot method. If the game isn't running at startup,
the window bind is deferred — apps will re-bind when they start.

**Important**: the framework is designed for dedicated foreground automation
runs. When an app runs, it takes the game to the foreground and controls it
exclusively. Claude should orchestrate at the `start_app` level, not try to
tap keys or take screenshots interactively.
