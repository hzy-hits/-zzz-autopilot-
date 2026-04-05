"""Shared navigation helpers for MCP tools."""

from __future__ import annotations

import asyncio
from typing import Any


async def navigate_to_screen(z_ctx: Any, screen_name: str) -> dict[str, Any]:
    """Navigate to target screen with framework routing graph."""
    screen_loader = getattr(z_ctx, "screen_loader", None)
    controller = getattr(z_ctx, "controller", None)
    if screen_loader is None:
        return {"navigated": False, "reason": "screen loader unavailable", "from": None, "to": screen_name}
    if controller is None:
        return {"navigated": False, "reason": "controller unavailable", "from": None, "to": screen_name}

    from one_dragon.base.screen import screen_utils

    timestamp, screen = await asyncio.to_thread(controller.screenshot)
    if screen is None:
        return {"navigated": False, "reason": "screenshot unavailable", "from": None, "to": screen_name}

    current_name = screen_loader.current_screen_name
    if current_name is None:
        current_name = await asyncio.to_thread(screen_utils.get_match_screen_name, z_ctx, screen)
        if current_name is not None:
            await asyncio.to_thread(screen_loader.update_current_screen_name, current_name)

    if current_name == screen_name:
        return {"navigated": True, "from": current_name, "to": screen_name, "timestamp": timestamp}

    if current_name is None:
        return {
            "navigated": False,
            "reason": "current screen could not be identified",
            "from": None,
            "to": screen_name,
        }

    route = await asyncio.to_thread(screen_loader.get_screen_route, current_name, screen_name)
    if route is None or not route.can_go:
        return {
            "navigated": False,
            "reason": f"no route from {current_name} to {screen_name}",
            "from": current_name,
            "to": screen_name,
        }

    for node in route.node_list:
        _ts, current_screen = await asyncio.to_thread(controller.screenshot)
        if current_screen is None:
            return {
                "navigated": False,
                "reason": "screenshot unavailable during navigation",
                "from": current_name,
                "to": screen_name,
            }

        click_result = await asyncio.to_thread(
            screen_utils.find_and_click_area,
            z_ctx,
            current_screen,
            node.from_screen,
            node.from_area,
        )
        if getattr(click_result, "name", "") == "AREA_NO_CONFIG":
            return {
                "navigated": False,
                "reason": f"missing area config: {node.from_screen}.{node.from_area}",
                "from": current_name,
                "to": screen_name,
            }
        if getattr(click_result, "name", "") not in {"OCR_CLICK_SUCCESS", "TRUE", "SUCCESS"} and "SUCCESS" not in str(
            click_result
        ):
            return {
                "navigated": False,
                "reason": f"failed to click route node: {node.from_screen}.{node.from_area}",
                "from": current_name,
                "to": screen_name,
                "click_result": str(click_result),
            }

        await asyncio.to_thread(screen_loader.update_current_screen_name, node.to_screen)
        current_name = node.to_screen
        await asyncio.sleep(0.12)

    final_timestamp, final_screen = await asyncio.to_thread(controller.screenshot)
    matched_name = await asyncio.to_thread(screen_utils.get_match_screen_name, z_ctx, final_screen)
    if matched_name != screen_name:
        return {
            "navigated": False,
            "reason": "arrival verification failed",
            "from": getattr(route, "from_screen", current_name),
            "to": screen_name,
            "observed": matched_name,
            "timestamp": final_timestamp,
        }
    return {
        "navigated": True,
        "from": getattr(route, "from_screen", current_name),
        "to": screen_name,
        "timestamp": final_timestamp,
    }
