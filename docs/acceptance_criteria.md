# ZZZ-Agent Acceptance Criteria

Each module has testable criteria. Codex should implement the `TODO(codex)` items
and verify against these criteria.

---

## Module 1: Server Infrastructure (`server/`)

**Already implemented:** mcp_server.py, context.py, event_stream.py

### Verify:
- [ ] `python -m zzz_agent.main --no-framework --port 8399` starts without errors
- [ ] MCP client can connect to `http://localhost:8399/sse`
- [ ] All 36 tools are discoverable via MCP tool listing
- [ ] `--no-framework` mode: tools that need the framework return clear error messages (not crashes)
- [ ] EventStream.push() delivers events to all subscribers
- [ ] EventStream.get_recent_events() returns history

---

## Module 2: Perception Tools (`tools/perception.py`, `state/extractor.py`)

### `get_screenshot`
- [ ] Returns base64-encoded PNG string
- [ ] Uses `z_ctx.controller.screenshot()` -> numpy array -> cv2.imencode -> base64
- [ ] Returns error dict (not exception) when game window is not ready

### `get_screen_state`
- [ ] Returns `{"screen_name": str, "ocr_text": str}`
- [ ] Uses `z_ctx.screen_loader.current_screen_name`
- [ ] Works without OCR (screen_name only) if OCR fails

### `get_daily_summary`
- [ ] Iterates all registered app factories
- [ ] For each: reads RunRecord via `get_run_record(app_id, instance_idx)`
- [ ] Maps `STATUS_WAIT=0, SUCCESS=1, FAIL=2, RUNNING=3` to human-readable strings
- [ ] Returns count of completed vs total
- [ ] Handles apps with no RunRecord gracefully

### `get_app_status(app_id)`
- [ ] Returns RunRecord fields: status, last_run_time, is_done
- [ ] Returns error dict if app_id is not registered

### `get_player_state(category)`
- [ ] `"stamina"`: extracts current/max from main UI screenshot + OCR
- [ ] `"characters"`: navigates to character panel, extracts name/level/ascension
- [ ] `"inventory"`: navigates to inventory, extracts material names/quantities
- [ ] Each category returns structured dict, not raw OCR text
- [ ] Handles OCR failures gracefully (returns partial data with errors list)

### `get_game_info`
- [ ] Returns game_window_ready boolean from controller
- [ ] Includes stamina if extractable
- [ ] Returns partial data on failure (not empty dict)

---

## Module 3: Dispatch Tools (`tools/dispatch.py`)

### `start_app(app_id)`
- [ ] Checks `run_context._run_state == STOP` before starting
- [ ] Returns `{"started": false, "reason": "another app is running"}` if busy
- [ ] Calls `run_context.run_application_async(app_id, instance_idx)`
- [ ] Applies config overrides if provided: `get_config() -> modify -> save`
- [ ] Pushes event on start

### `stop_app`
- [ ] Calls `run_context.stop_running()`
- [ ] Returns `{"stopped": false}` if no app is running
- [ ] Pushes event on stop

### `pause_app` / `resume_app`
- [ ] Uses `run_context.pause_resume()` (toggle)
- [ ] Returns error if app is not in the expected state

### `retry_app(app_id, config)`
- [ ] Stops current app, waits briefly, starts with new config
- [ ] Equivalent to stop_app + start_app sequence

### `switch_instance(idx)` / `list_instances`
- [ ] switch: calls `z_ctx.switch_instance(idx)`
- [ ] list: reads from `z_ctx.one_dragon_config.instance_list`

---

## Module 4: Input Tools (`tools/input.py`)

### `click(x, y)`
- [ ] Creates `Point(x, y)` and calls `controller.click(point, press_time)`
- [ ] All controller calls wrapped in `asyncio.to_thread()`

### `tap_key(key)` / `press_key(key, duration)`
- [ ] Maps string key names to framework key enums
- [ ] Calls `controller.btn_tap()` or `controller.btn_press()`

### `drag`, `scroll`, `input_text`
- [ ] Direct delegation to controller methods
- [ ] Proper coordinate handling

### `navigate_to(screen_name)`
- [ ] Uses framework screen routing to find path
- [ ] Executes navigation steps
- [ ] Verifies arrival

### `find_and_click(screen_name, area_name)`
- [ ] Gets ScreenArea from screen_loader
- [ ] Template matches on current screenshot
- [ ] Clicks center of matched area
- [ ] Returns found=false if template match fails

### `resolve_intervention(id, action)`
- [ ] Calls `intervention_queue.resolve(id, action)`
- [ ] Returns `{"resolved": false}` if intervention not found

---

## Module 5: Knowledge System (`knowledge/`)

**Already implemented:** service.py (basic), rag.py (stub)

### KnowledgeService
- [ ] Loads all YAML files from `config/game_knowledge/core/`
- [ ] `query("stamina")` returns stamina data from stamina.yml
- [ ] `query("Lina")` returns character data from characters.yml
- [ ] `update_discovered(key, value)` writes to `discovered_knowledge/{key}.yml`
- [ ] Discovered knowledge is tagged `verified: false`
- [ ] Query priority: core data > discovered data
- [ ] `reload()` refreshes from disk

### RAGIndex (TODO for Codex)
- [ ] `build_index()` reads all .md files from guides/
- [ ] Splits into 200-500 token chunks with overlap
- [ ] Persists index to disk
- [ ] `search(query, top_k)` returns relevant excerpts with scores
- [ ] Returns empty list (not error) when index doesn't exist

---

## Module 6: Goal System (`goals/`)

**Already implemented:** manager.py

### GoalManager
- [ ] `add_goal("Level Lina to 60", "high")` creates goal with UUID-based ID
- [ ] `list_goals()` returns goals sorted by priority (high first)
- [ ] `update_goal(id, status="completed")` persists to goals.yml
- [ ] `remove_goal(id)` deletes from goals.yml
- [ ] Goals persist across process restarts
- [ ] Invalid goal_id returns None (not exception)

---

## Module 7: Planning System (`planning/`)

**Already implemented:** store.py

### PlanStore
- [ ] `create_plan(goal, steps)` creates plan with auto-generated ID
- [ ] Creating a new plan cancels any existing active plan
- [ ] `get_active_plan()` returns the current active plan
- [ ] `update_step(step_id, "completed")` updates step status
- [ ] Plan auto-completes when all steps are completed/skipped
- [ ] Plans persist as individual YAML files in `config/plans/`
- [ ] Plans survive process restart
- [ ] `list_plans()` returns recent plans sorted by date

---

## Module 8: Intervention System (`intervention/`)

**Already implemented:** queue.py, patches.py

### InterventionQueue
- [ ] `request()` blocks the calling thread until resolved or timeout
- [ ] `resolve(id, action)` unblocks the blocked thread
- [ ] `list_pending()` returns all unresolved requests
- [ ] Timed-out requests auto-resolve with "timeout" resolution
- [ ] Thread-safe: concurrent requests from multiple framework threads

### Monkey-Patch
- [ ] `apply_patches()` returns False when framework is not importable
- [ ] Original `send_node_notify` behavior is preserved
- [ ] Triggers intervention on: node FAIL + SCREEN_UNKNOWN
- [ ] Triggers intervention on: node FAIL + retries exhausted
- [ ] Captures screenshot as base64 before creating intervention
- [ ] Pushes SSE event when intervention is triggered
- [ ] Pauses app before blocking, resumes after resolution

---

## Integration Tests

### Dev Mode (no framework)
```bash
python -m zzz_agent.main --no-framework --port 8399
# Then from another terminal:
# - MCP client connects
# - get_goals() returns empty list
# - add_goal("test", "high") succeeds
# - get_goals() returns the added goal
# - query_game_knowledge("stamina") returns stamina data
# - create_execution_plan("test", [...]) succeeds
# - get_execution_plan() returns the plan
# - Framework-dependent tools return clear error messages
```

### With Framework (Windows)
```bash
set PYTHONPATH=C:\path\to\ZenlessZoneZero-OneDragon\src
python -m zzz_agent.main --port 8399
# - All tools work
# - get_screenshot() returns valid base64 image
# - start_app("coffee") launches the coffee shop automation
# - Intervention triggers when an app encounters unknown screen
```

---

## Code Quality
- [ ] `uv run ruff check src/` passes with no errors
- [ ] `uv run ruff format --check src/` passes
- [ ] All public functions have type hints
- [ ] All MCP tools have docstrings with Args/Returns
- [ ] No framework imports at module level (all lazy or guarded)
- [ ] `uv run pytest` passes
