"""Failure analysis MCP tools.

Understanding WHY things failed. These tools provide rich context for the
Agent to diagnose issues and adjust strategy.
"""

from __future__ import annotations

import asyncio
import base64
import io
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from zzz_agent.server.context import get_agent_ctx

_LOG_LINE_RE = re.compile(
    r"^\[(?P<timestamp>[^\]]+)\]\s+\[(?P<file>[^\s]+)\s+(?P<line>\d+)\]\s+\[(?P<level>[A-Z]+)\]:\s+(?P<message>.*)$"
)


def _framework_error(reason: str) -> dict[str, Any]:
    return {"found": False, "status": "error", "reason": reason}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _log_file_candidates() -> list[Path]:
    candidates = [
        Path.cwd() / ".log" / "log.txt",
        _repo_root() / ".log" / "log.txt",
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _read_log_text_sync() -> tuple[Path | None, str]:
    for path in _log_file_candidates():
        if path.exists():
            try:
                return path, path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return path, ""
    return None, ""


def _parse_log_lines(text: str, tokens: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    normalized_tokens = [token.lower() for token in tokens if token]
    if not normalized_tokens:
        return entries

    for raw_line in text.splitlines():
        lowered = raw_line.lower()
        if not any(token in lowered for token in normalized_tokens):
            continue

        match = _LOG_LINE_RE.match(raw_line)
        if match is None:
            entries.append(
                {
                    "timestamp": None,
                    "level": "INFO",
                    "message": raw_line.strip(),
                    "raw": raw_line,
                }
            )
            continue

        entries.append(
            {
                "timestamp": match.group("timestamp"),
                "level": match.group("level"),
                "message": match.group("message"),
                "file": match.group("file"),
                "line": int(match.group("line")),
                "raw": raw_line,
            }
        )
    return entries


def _app_log_tokens(ctx: Any, app_id: str) -> list[str]:
    tokens = [app_id]
    run_context = getattr(getattr(ctx, "z_ctx", None), "run_context", None)
    if run_context is not None:
        try:
            app_name = run_context.get_application_name(app_id)
        except Exception:
            app_name = None
        if app_name:
            tokens.append(str(app_name))
    return list(dict.fromkeys(token for token in tokens if token))


def _encode_png_base64(image: Any) -> str | None:
    if image is None:
        return None

    try:
        from PIL import Image
    except Exception:
        Image = None  # type: ignore[assignment]

    try:
        import numpy as np
    except Exception:
        np = None  # type: ignore[assignment]

    try:
        if Image is not None:
            if np is not None and hasattr(image, "shape"):
                mode = "RGB" if len(image.shape) == 3 and image.shape[2] in {3, 4} else "L"
                pil_img = Image.fromarray(image.astype("uint8"), mode=mode)  # type: ignore[union-attr]
            else:
                pil_img = (
                    image if isinstance(image, Image.Image) else Image.frombytes("RGB", image.size, image.tobytes())
                )  # type: ignore[attr-defined]
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        pass

    return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _status_label(status: Any) -> str:
    mapping = {
        0: "waiting",
        1: "success",
        2: "failed",
        3: "running",
    }
    if isinstance(status, str):
        normalized = status.strip().lower()
        return normalized or "unknown"
    return mapping.get(status, "unknown")


def _get_instance_idx(ctx) -> int:
    for attr in ("current_instance_idx",):
        value = getattr(ctx.z_ctx, attr, None)
        if value is not None:
            return _safe_int(value, 0)
    one_dragon = getattr(ctx.z_ctx, "one_dragon_config", None)
    current_active = getattr(one_dragon, "current_active_instance", None)
    if current_active is not None and getattr(current_active, "idx", None) is not None:
        return _safe_int(current_active.idx, 0)
    return 0


async def _get_run_record(ctx, app_id: str):
    run_context = ctx.z_ctx.run_context
    instance_idx = _get_instance_idx(ctx)
    return await asyncio.to_thread(run_context.get_run_record, app_id, instance_idx)


def _summarize_run_record(run_record: Any) -> dict[str, Any]:
    return {
        "status": _status_label(getattr(run_record, "run_status_under_now", getattr(run_record, "run_status", None))),
        "run_status": getattr(run_record, "run_status", None),
        "run_status_under_now": getattr(run_record, "run_status_under_now", None),
        "run_time": getattr(run_record, "run_time", None),
        "run_time_float": getattr(run_record, "run_time_float", None),
        "is_done": bool(getattr(run_record, "is_done", False)),
        "dt": getattr(run_record, "dt", None),
    }


def _extract_failure_hints(app_id: str, log_entries: list[dict[str, Any]], run_record: Any) -> dict[str, Any]:
    last_error = None
    last_warning = None
    last_node = getattr(run_record, "last_node_name", None) or getattr(run_record, "current_node_name", None)
    last_node_status = getattr(run_record, "last_node_status", None)

    for entry in reversed(log_entries):
        message = str(entry.get("message", ""))
        level = str(entry.get("level", ""))
        if last_error is None and level == "ERROR":
            last_error = message
        if last_warning is None and level == "WARNING":
            last_warning = message
        if last_node is None:
            node_match = re.search(r"(?:node|节点)\s*[:=]\s*([^\s,;]+)", message, re.IGNORECASE)
            if node_match:
                last_node = node_match.group(1)
        if last_node_status is None:
            status_match = re.search(r"(SCREEN_UNKNOWN|RETRIES_EXHAUSTED|FAIL|ERROR|TIMEOUT)", message, re.IGNORECASE)
            if status_match:
                last_node_status = status_match.group(1).upper()

    return {
        "last_node": last_node,
        "last_node_status": last_node_status,
        "last_error": last_error,
        "last_warning": last_warning,
    }


def _get_last_screenshot_sync(ctx) -> Any:
    candidates = [
        getattr(ctx.z_ctx, "last_screenshot", None),
        getattr(getattr(ctx.z_ctx, "run_context", None), "last_screenshot", None),
        getattr(getattr(ctx.z_ctx, "controller", None), "last_screenshot", None),
    ]
    for candidate in candidates:
        if candidate is not None:
            return candidate

    controller = getattr(ctx.z_ctx, "controller", None)
    if controller is None or not getattr(controller, "is_game_window_ready", False):
        return None

    try:
        _, image = controller.screenshot()
        return image
    except Exception:
        return None


def register_tools(mcp: FastMCP) -> None:
    """Register all analysis tools on the MCP server."""

    @mcp.tool()
    async def get_failure_detail(app_id: str) -> dict[str, Any]:
        """Get rich failure context for a failed app run."""
        ctx = get_agent_ctx()
        if ctx.z_ctx is None:
            return _framework_error("framework not available")

        try:
            is_registered = await asyncio.to_thread(ctx.z_ctx.run_context.is_app_registered, app_id)
            if not is_registered:
                return {"found": False, "app_id": app_id, "status": "error", "reason": f"app not registered: {app_id}"}

            run_record = await _get_run_record(ctx, app_id)
            if hasattr(run_record, "check_and_update_status"):
                await asyncio.to_thread(run_record.check_and_update_status)

            log_path, log_text = await asyncio.to_thread(_read_log_text_sync)
            log_entries = _parse_log_lines(log_text, _app_log_tokens(ctx, app_id))
            hints = _extract_failure_hints(app_id, log_entries, run_record)
            screenshot = await asyncio.to_thread(_get_last_screenshot_sync, ctx)
            screenshot_b64 = await asyncio.to_thread(_encode_png_base64, screenshot)

            duration_seconds = None
            run_time_float = getattr(run_record, "run_time_float", None)
            if run_time_float:
                duration_seconds = max(0.0, float(datetime.now().timestamp() - float(run_time_float)))

            failure_time = getattr(run_record, "run_time", None)
            result = {
                "found": True,
                "app_id": app_id,
                "app_name": getattr(ctx.z_ctx.run_context, "get_application_name", lambda _app_id: app_id)(app_id),
                "status": _status_label(getattr(run_record, "run_status", None)),
                "run_record": _summarize_run_record(run_record),
                "last_node": hints["last_node"],
                "last_node_status": hints["last_node_status"],
                "screenshot_base64": screenshot_b64,
                "retry_count": getattr(run_record, "retry_count", None),
                "max_retries": getattr(run_record, "max_retries", None),
                "error_log": "\n".join(entry["raw"] for entry in log_entries[-20:]),
                "log_path": str(log_path) if log_path is not None else None,
                "duration_seconds": duration_seconds,
                "failure_time": failure_time,
            }
            if hints["last_error"] is not None:
                result["last_error"] = hints["last_error"]
            if hints["last_warning"] is not None:
                result["last_warning"] = hints["last_warning"]
            return result
        except Exception as exc:
            return {
                "found": False,
                "app_id": app_id,
                "status": "error",
                "reason": str(exc),
                "traceback": traceback.format_exc(),
            }

    @mcp.tool()
    async def get_app_execution_log(app_id: str, last_n: int = 50) -> list[dict[str, Any]]:
        """Get recent execution log entries for an app."""
        try:
            ctx = get_agent_ctx()
            _, log_text = await asyncio.to_thread(_read_log_text_sync)
            entries = _parse_log_lines(log_text, _app_log_tokens(ctx, app_id))
            if last_n > 0:
                entries = entries[-last_n:]
            return entries
        except Exception:
            return []

    @mcp.tool()
    async def get_pending_interventions() -> list[dict[str, Any]]:
        """List intervention requests waiting for Agent decision."""
        ctx = get_agent_ctx()
        if ctx.interventions is None:
            return []
        return [i.to_dict() for i in ctx.interventions.list_pending()]
