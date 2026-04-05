# ZZZ-Agent Acceptance Criteria

Per-module testable criteria. Use this as a verification checklist when a module
claims to be complete. For current priorities and known bugs, see [../TODO.md](../TODO.md).

**Status legend:**
- ✅ Implemented & tested (unit tests passing)
- 🔧 Implemented, has known bugs (see TODO.md P1)
- 🚧 Partial / stub — needs work
- ⏳ Not started

---

## Module 1: Server Infrastructure (`server/`) ✅

### Verify:
- [x] `python -m zzz_agent.main --no-framework --transport sse --port 8399` starts without errors
- [x] MCP client can connect to `http://localhost:8399/sse`
- [x] All tools are discoverable via MCP tool listing
- [x] `--no-framework` mode: tools that need the framework return clear error messages (not crashes)
- [x] `EventStream.push()` delivers events to all subscribers
- [x] `EventStream` history buffer returns recent events
- [ ] **Known issue**: SSE subscribers not cleaned up on disconnect (memory leak, TODO.md P2)

---

## Module 2: Perception Tools (`tools/perception.py`, `state/extractor.py`) 🔧

### `get_screenshot` 🔧
- [x] Returns base64-encoded PNG string
- [x] Uses `z_ctx.controller.screenshot()` -> numpy array -> cv2.imencode -> base64
- [x] Returns error dict (not exception) when game window is not ready
- [ ] **Blocked until P0 verified**: `controller.init_before_context_run()` must be called (fixed in main.py, needs server restart to verify)

### `get_screen_state` ✅
- [x] Returns `{"screen_name": str, "ocr_text": str, "confidence": float}`
- [x] Uses `z_ctx.screen_loader.current_screen_name`
- [x] Works without OCR (screen_name only) if OCR fails

### `get_daily_summary` ✅
- [x] Iterates all registered app factories
- [x] For each: reads RunRecord via `get_run_record(app_id, instance_idx)`
- [x] Maps `STATUS_WAIT=0, SUCCESS=1, FAIL=2, RUNNING=3` to human-readable strings
- [x] Returns count of completed vs total
- [x] Handles apps with no RunRecord gracefully

### `get_app_status(app_id)` ✅
- [x] Returns RunRecord fields: status, last_run_time, is_done
- [x] Returns error dict if app_id is not registered

### `get_player_state(category)` 🔧
- [x] `"stamina"`: extracts current/max from screenshot + OCR
- [x] `"characters"`: navigates to character panel, extracts name/level/ascension
- [x] `"inventory"`: navigates to inventory, extracts material names/quantities
- [x] `characters` also extracts rarity/element/weapon/skills on a best-effort basis
- [x] `equipment` parses slot/level/rarity/main_stat/sub_stats on a best-effort basis
- [x] `inventory` includes rarity parsing when OCR text contains it
- [x] Each category returns structured dict with `errors` list on partial failure
- [x] OCR backend failures are surfaced in `errors` with backend-specific context

### `get_game_info` ✅
- [x] Returns `game_window_ready` boolean from controller
- [x] Includes stamina if extractable
- [x] Returns partial data with `errors` on failure (not empty dict)

---

## Module 3: Dispatch Tools (`tools/dispatch.py`) 🔧

### `start_app(app_id, config, instance_idx)` 🔧
- [x] Checks `run_context._run_state == STOP` before starting
- [x] Returns error when another app is already running
- [x] Calls `run_context.run_application_async(app_id, instance_idx, group_id)`
- [x] Applies config overrides with deep-merge
- [x] Pushes event on start
- [x] Waits for `ctx.ready_for_application` before dispatch, returning a clear error on timeout/failure

### `stop_app` ✅
- [x] Calls `run_context.stop_running()`
- [x] Returns error if no app is running
- [x] Pushes event on stop

### `pause_app` / `resume_app` ✅
- [x] Uses `run_context.switch_context_pause_and_run()` / equivalent toggle
- [x] Returns error if app is not in expected state

### `retry_app(app_id, config)` ✅
- [x] Stops current app, restarts with new config
- [x] Equivalent to stop_app + start_app sequence

### `switch_instance(idx)` / `list_instances` 🔧
- [x] switch: calls `z_ctx.switch_instance(idx)`
- [x] list: reads from `z_ctx.one_dragon_config.instance_list`
- [x] switch re-runs `init_for_application()` afterward and reports readiness/warnings

---

## Module 4: Input Tools (`tools/input.py`) 🔧

### `click(x, y, press_time)` 🔧
- [x] Creates `Point(x, y)` and calls `controller.click(point, press_time)`
- [x] All controller calls wrapped in `asyncio.to_thread()`
- [x] Fails fast when `is_game_window_ready` is false

### `tap_key(key)` / `press_key(key, duration)` 🔧
- [x] Maps string key names (including aliases: esc, enter, etc.)
- [x] Calls `controller.btn_tap()` or `controller.btn_press()`
- [x] Fails fast when `is_game_window_ready` is false

### `drag`, `scroll`, `input_text` 🔧
- [x] Direct delegation to controller methods
- [x] Proper coordinate handling
- [x] `scroll` validates/falls back to a concrete center point and returns an error if unavailable

### `navigate_to(screen_name)` 🔧
- [x] Uses framework screen routing
- [x] Executes navigation steps
- [x] Re-verifies with a fresh screenshot even when `current_screen_name` already matches
- [x] Enforces a max-step safeguard on route traversal
- [x] Checks that the final screenshot exists before arrival verification

### `find_and_click(screen_name, area_name)` ✅
- [x] Gets ScreenArea from screen_loader
- [x] Template matches on current screenshot
- [x] Clicks center of matched area
- [x] Returns `found=false` if template match fails

### `resolve_intervention(id, action)` ✅
- [x] Calls `intervention_queue.resolve(id, action)`
- [x] Returns error if intervention not found

---

## Module 5: Knowledge System (`knowledge/`) ✅

### KnowledgeService ✅
- [x] Loads YAML files from `config/game_knowledge/core/`
- [x] Three-layer query: framework → remote → discovered
- [x] `query("stamina")` returns stamina data
- [x] `query("Lina")` returns character data
- [x] `update_discovered(key, value)` writes to `discovered_knowledge/{key}.yml`
- [x] Discovered knowledge tagged unverified
- [x] Source attribution on query result
- [x] `reload()` refreshes from disk
- [ ] **TODO**: Remote URL config is still a placeholder (TODO.md P2)
- [ ] **Known issue**: `_search_framework` has no caching, slow on large configs (TODO.md P2)

### RAGIndex ✅
- [x] `build_index()` reads all .md files from guides/
- [x] Splits into 200-500 token chunks with overlap
- [x] Persists index to disk with manifest (mtime-based staleness)
- [x] `search(query, top_k)` returns ranked excerpts
- [x] TF-IDF + cosine similarity (no embeddings, adequate for structured docs)
- [ ] **Known issue**: `build_index` is sync I/O, should be wrapped in `to_thread` (TODO.md P2)

---

## Module 6: Goal System (`goals/`) ✅

### GoalManager ✅
- [x] `add_goal("Level Lina to 60", "high")` creates goal with UUID
- [x] `list_goals()` returns goals sorted by priority (high first)
- [x] `update_goal(id, status="completed")` persists to goals.yml
- [x] `remove_goal(id)` deletes from goals.yml
- [x] Goals persist across process restarts
- [x] Invalid goal_id returns None
- [ ] **Known issue**: YAML read/write has no file lock (TODO.md P2)

---

## Module 7: Planning System (`planning/`) 🔧

### PlanStore ✅
- [x] `create_plan(goal, steps)` creates plan with auto-generated ID
- [x] Creating a new plan cancels any existing active plan
- [x] `get_active_plan()` returns the current active plan
- [x] `update_step(step_id, "completed")` updates step status
- [x] Plan auto-completes when all steps completed/skipped
- [x] Plans persist as individual YAML files in `config/plans/`
- [x] Plans survive process restart
- [x] `list_plans()` returns recent plans sorted by date
- [ ] **Known issue**: No file lock on concurrent updates (TODO.md P2)

---

## Module 8: Intervention System (`intervention/`) 🔧

### InterventionQueue ✅
- [x] `request()` blocks calling thread until resolved or timeout
- [x] `resolve(id, action)` unblocks the blocked thread
- [x] `list_pending()` returns all unresolved requests
- [x] Timed-out requests auto-resolve with `"timeout"` resolution
- [x] Thread-safe with RLock
- [ ] **Known issue**: Race between timeout expiry and late resolution (TODO.md P2)

### Monkey-Patch ✅
- [x] `apply_patches()` returns False when framework not importable
- [x] Original `send_node_notify` behavior preserved (called first)
- [x] Detects SCREEN_UNKNOWN and retry-exhausted conditions
- [x] Captures screenshot as base64 before creating intervention
- [x] Pushes SSE event when intervention triggered
- [x] Pauses app before blocking, resumes after resolution
- [x] Verified against framework source that `round_result.result` uses `OperationRoundResultEnum.FAIL`
- [x] Uses framework `Operation.STATUS_SCREEN_UNKNOWN` constant first, with compatibility fallbacks
- [x] Only pauses/resumes when run state permits
- [x] Returns/logs `None` explicitly when screenshot encoding fails

---

## Integration Tests

### Dev Mode (no framework)
```bash
python -m zzz_agent.main --no-framework --transport sse --port 8399
# From another terminal:
# - MCP client connects
# - get_goals() returns empty list
# - add_goal("test", "high") succeeds
# - query_game_knowledge("stamina") returns stamina data
# - create_execution_plan("test", [...]) succeeds
# - Framework-dependent tools return clear "framework unavailable" errors
```

### With Framework (Windows)
```powershell
.\start.ps1
# - Framework initializes, game window bound (check log for "Game window bound successfully")
# - get_screenshot() returns valid base64 image of the actual game
# - get_game_info() returns real stamina values
# - list_available_apps() returns all registered apps with status
# - start_app("email") launches the mail automation
# - get_daily_summary() reflects completion after run
# - Intervention triggers when an app encounters SCREEN_UNKNOWN
```

---

## Code Quality

- [x] `uv run ruff check src/` passes with no errors
- [x] `uv run ruff format --check src/` passes
- [x] All public functions have type hints
- [x] All MCP tools have docstrings
- [x] No framework imports at module level (all lazy or guarded)
- [x] `uv run pytest` passes (7/7 test modules)
