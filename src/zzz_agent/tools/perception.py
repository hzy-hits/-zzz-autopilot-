"""State perception MCP tools."""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
from typing import Any

from mcp.server.fastmcp import FastMCP

from zzz_agent.server.context import get_agent_ctx
from zzz_agent.state.extractor import ExtractionResult, StateExtractor
from zzz_agent.tools.navigation import navigate_to_screen


def _error(message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "error": message}
    payload.update(extra)
    return payload


def _status_label(raw_status: Any) -> str:
    mapping = {
        0: "not_run",
        1: "completed",
        2: "failed",
        3: "running",
        "WAIT": "not_run",
        "SUCCESS": "completed",
        "FAIL": "failed",
        "RUNNING": "running",
    }
    return mapping.get(getattr(raw_status, "value", raw_status), str(raw_status).lower())


def _active_instance_idx(ctx: Any) -> int:
    if getattr(ctx, "current_instance_idx", None) is not None:
        return int(ctx.current_instance_idx)
    one_dragon_config = getattr(ctx, "one_dragon_config", None)
    if one_dragon_config is not None:
        current = getattr(one_dragon_config, "current_active_instance", None)
        if current is not None:
            return int(current.idx)
    return 0


def _factory_list(run_context: Any) -> list[tuple[str, Any]]:
    factory_map = getattr(run_context, "_application_factory_map", {})
    if not isinstance(factory_map, dict):
        return []
    return list(factory_map.items())


async def _capture_screenshot(ctx: Any) -> tuple[float, Any]:
    controller = getattr(ctx, "controller", None)
    if controller is None:
        raise RuntimeError("controller is not available")

    # If the game was launched after the MCP server started, init_before_context_run()
    # couldn't find the game window, so screenshot_controller.init_screenshot() was never
    # called. init_game_win() is idempotent (re-finds window, re-inits screenshot method),
    # so always run it to handle late-launch scenarios.
    init_game_win = getattr(controller, "init_game_win", None)
    if init_game_win is not None:
        await asyncio.to_thread(init_game_win)

    return await asyncio.to_thread(controller.screenshot)


async def _ocr_text(ctx: Any, image: Any) -> str:
    ocr_service = getattr(ctx, "ocr_service", None)
    if ocr_service is None:
        return ""

    def _run() -> str:
        try:
            result_list = ocr_service.get_ocr_result_list(image)
            parts: list[str] = []
            for item in result_list:
                data = getattr(item, "data", None)
                if data:
                    parts.append(str(data))
            if parts:
                return " ".join(parts)
        except Exception:
            pass

        ocr = getattr(ctx, "ocr", None)
        if ocr is None:
            return ""
        try:
            return str(ocr.run_ocr_single_line(image))
        except Exception:
            return ""

    return await asyncio.to_thread(_run)


def _extraction_payload(result: ExtractionResult) -> dict[str, Any]:
    payload = dict(result.data)
    if result.raw_ocr_text:
        payload["raw_ocr_text"] = result.raw_ocr_text
    if result.errors:
        payload["errors"] = result.errors
    return payload


def _state_payload(result: dict[str, Any], errors: list[str] | None = None) -> dict[str, Any]:
    payload = dict(result)
    if errors:
        payload["errors"] = errors
    return payload


def register_tools(mcp: FastMCP) -> None:
    """Register all perception tools on the MCP server."""

    @mcp.tool()
    async def get_player_state(category: str) -> dict[str, Any]:
        """Navigate to game panels and extract structured player state via screenshot + OCR."""
        ctx = get_agent_ctx()
        z_ctx = getattr(ctx, "z_ctx", None)
        if z_ctx is None:
            return _error("framework unavailable", category=category)
        if getattr(z_ctx, "controller", None) is None:
            return _error("controller unavailable", category=category)

        category_l = category.lower()
        extractor = StateExtractor(z_ctx)
        errors: list[str] = []
        try:
            if category_l != "stamina":
                targets = {
                    "characters": ["character", "characters", "角色", "角色界面"],
                    "inventory": ["inventory", "backpack", "bag", "背包"],
                    "equipment": ["equipment", "drive_disc", "装备", "驱动盘"],
                    "shop": ["shop", "商店", "商店界面"],
                }.get(category_l, [])

                navigated = False
                for target in targets:
                    nav_result = await navigate_to_screen(z_ctx, target)
                    if nav_result.get("navigated"):
                        navigated = True
                        break
                if not navigated and targets:
                    errors.append(f"could not navigate to {category_l}")

            if category_l == "stamina":
                result = await extractor.extract_stamina()
                if errors:
                    result.errors = (result.errors or []) + errors
                return _extraction_payload(result)

            if category_l == "characters":
                result = await extractor.extract_characters()
                if errors:
                    result.errors = (result.errors or []) + errors
                return _extraction_payload(result)

            if category_l == "inventory":
                result = await extractor.extract_inventory()
                if errors:
                    result.errors = (result.errors or []) + errors
                return _extraction_payload(result)

            if category_l == "equipment":
                result = await extractor.extract_equipment()
                if errors:
                    result.errors = (result.errors or []) + errors
                return _extraction_payload(result)

            _, image = await _capture_screenshot(z_ctx)
            text = await _ocr_text(z_ctx, image)
            if category_l == "shop":
                lines = [segment.strip() for segment in text.splitlines() if segment.strip()]
                return _state_payload({"shop_items": lines, "raw_ocr_text": text}, errors or None)

            return _error("unsupported category", category=category)
        except Exception as exc:
            return _error(f"failed to extract {category}", detail=f"{type(exc).__name__}: {exc}")

    @mcp.tool()
    async def get_screenshot() -> str | dict[str, Any]:
        """Get current game screenshot as base64-encoded PNG."""
        ctx = get_agent_ctx()
        z_ctx = getattr(ctx, "z_ctx", None)
        if z_ctx is None or getattr(z_ctx, "controller", None) is None:
            return _error("framework unavailable")

        try:
            _, image = await _capture_screenshot(z_ctx)
            if image is None:
                return _error("screenshot unavailable")

            def _encode() -> str:
                import cv2

                ok, buf = cv2.imencode(".png", image)
                if not ok:
                    raise RuntimeError("cv2.imencode failed")
                return base64.b64encode(buf).decode("utf-8")

            return await asyncio.to_thread(_encode)
        except Exception as exc:
            return _error("failed to capture screenshot", detail=f"{type(exc).__name__}: {exc}")

    @mcp.tool()
    async def get_screen_state() -> dict[str, Any]:
        """Get current screen identification and OCR text."""
        ctx = get_agent_ctx()
        z_ctx = getattr(ctx, "z_ctx", None)
        if z_ctx is None:
            return _error("framework unavailable")

        screen_name = getattr(getattr(z_ctx, "screen_loader", None), "current_screen_name", None)
        text = ""
        errors: list[str] = []
        try:
            _, image = await _capture_screenshot(z_ctx)
            text = await _ocr_text(z_ctx, image)
        except Exception as exc:
            errors.append(f"ocr failed: {type(exc).__name__}: {exc}")

        payload = {"screen_name": screen_name, "ocr_text": text, "confidence": 0.0 if not text else 1.0}
        return _state_payload(payload, errors or None)

    @mcp.tool()
    async def get_daily_summary() -> dict[str, Any]:
        """Get today's task completion summary across all apps."""
        ctx = get_agent_ctx()
        z_ctx = getattr(ctx, "z_ctx", None)
        if z_ctx is None or getattr(z_ctx, "run_context", None) is None:
            return _error("framework unavailable")

        run_context = z_ctx.run_context
        instance_idx = _active_instance_idx(z_ctx)
        apps: list[dict[str, Any]] = []
        completed_count = 0

        for app_id, factory in sorted(_factory_list(run_context), key=lambda item: item[0]):
            try:
                run_record = await asyncio.to_thread(run_context.get_run_record, app_id, instance_idx)
                status_value = getattr(run_record, "run_status_under_now", getattr(run_record, "run_status", 0))
                status = _status_label(status_value)
                if status == "completed":
                    completed_count += 1
                apps.append(
                    {
                        "app_id": app_id,
                        "name": getattr(factory, "app_name", app_id),
                        "status": status,
                        "run_time": getattr(run_record, "run_time", "-"),
                        "is_done": bool(getattr(run_record, "is_done", False)),
                    }
                )
            except Exception as exc:
                apps.append(
                    {
                        "app_id": app_id,
                        "name": getattr(factory, "app_name", app_id),
                        "status": "not_run",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

        return {
            "date": dt.datetime.now().strftime("%Y-%m-%d"),
            "apps": apps,
            "completed_count": completed_count,
            "total_count": len(apps),
        }

    @mcp.tool()
    async def get_app_status(app_id: str) -> dict[str, Any]:
        """Get detailed run record for a specific app."""
        ctx = get_agent_ctx()
        z_ctx = getattr(ctx, "z_ctx", None)
        if z_ctx is None or getattr(z_ctx, "run_context", None) is None:
            return _error("framework unavailable", app_id=app_id)

        run_context = z_ctx.run_context
        if not await asyncio.to_thread(run_context.is_app_registered, app_id):
            return _error("app not registered", app_id=app_id)

        try:
            run_record = await asyncio.to_thread(run_context.get_run_record, app_id, _active_instance_idx(z_ctx))
            status_value = getattr(run_record, "run_status_under_now", getattr(run_record, "run_status", 0))
            status = _status_label(status_value)
            payload = {
                "app_id": app_id,
                "status": status,
                "last_run_time": getattr(run_record, "run_time", "-"),
                "run_count_today": 1 if status != "not_run" else 0,
                "is_done": bool(getattr(run_record, "is_done", False)),
            }
            return payload
        except Exception as exc:
            return _error(f"failed to read run record for {app_id}", detail=f"{type(exc).__name__}: {exc}")

    @mcp.tool()
    async def get_game_info() -> dict[str, Any]:
        """Get basic game information: stamina, player level, server time."""
        ctx = get_agent_ctx()
        z_ctx = getattr(ctx, "z_ctx", None)
        if z_ctx is None:
            return _error("framework unavailable")

        game_window_ready = bool(getattr(getattr(z_ctx, "controller", None), "is_game_window_ready", False))
        stamina: dict[str, Any] = {"current": None, "max": None}
        errors: list[str] = []

        if game_window_ready:
            stamina_result = await StateExtractor(z_ctx).extract_stamina()
            stamina = {"current": stamina_result.data.get("current"), "max": stamina_result.data.get("max")}
            if stamina_result.errors:
                errors.extend([str(item) for item in stamina_result.errors])

        return {
            "stamina": stamina,
            "server_time": dt.datetime.now().isoformat(timespec="seconds"),
            "game_window_ready": game_window_ready,
            "errors": errors or None,
        }
