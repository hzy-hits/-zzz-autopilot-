"""Monkey-patch for the original framework's notification system.

Patches send_node_notify() to trigger intervention requests when:
  - A node fails with SCREEN_UNKNOWN status
  - A node exhausts its retry limit

This is the ONLY modification to the original framework's behavior.
The patch wraps the existing function, preserving all original behavior.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zzz_agent.intervention.queue import InterventionQueue
    from zzz_agent.server.event_stream import EventStream

logger = logging.getLogger(__name__)


def apply_patches(
    z_ctx: object,
    intervention_queue: InterventionQueue,
    event_stream: EventStream,
) -> bool:
    """Apply monkey-patch to the framework's send_node_notify function.

    Args:
        z_ctx: The framework's OneDragonContext instance.
        intervention_queue: Queue for creating intervention requests.
        event_stream: Event stream for pushing notifications.

    Returns:
        True if patch was applied successfully, False if framework not available.
    """
    try:
        from one_dragon.base.operation import operation_notify
        from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
    except ImportError:
        logger.warning("Framework modules not available. Skipping monkey-patch.")
        return False

    # Let queue emit intervention events, keeping source of truth in one place.
    with contextlib.suppress(Exception):
        intervention_queue.set_event_stream(event_stream)

    original_notify = operation_notify.send_node_notify

    def patched_notify(operation, round_result, current_node, next_node):
        # Always call original first
        original_notify(operation, round_result, current_node, next_node)

        # Check if intervention is needed
        should_intervene = False
        reason = ""

        if round_result.result == OperationRoundResultEnum.FAIL:
            # Unknown screen
            if hasattr(round_result, "status") and "unknown" in str(round_result.status).lower():
                should_intervene = True
                reason = f"SCREEN_UNKNOWN: {round_result.status}"

            # Retries exhausted
            elif hasattr(operation, "node_retry_times") and hasattr(operation, "node_max_retry_times"):
                if operation.node_retry_times >= operation.node_max_retry_times:
                    should_intervene = True
                    reason = f"RETRIES_EXHAUSTED: node={current_node.cn if current_node else 'unknown'}"

        if not should_intervene:
            return

        # Capture screenshot
        screenshot_b64 = None
        if hasattr(operation, "last_screenshot") and operation.last_screenshot is not None:
            try:
                import base64

                import cv2

                _, buf = cv2.imencode(".png", operation.last_screenshot)
                screenshot_b64 = base64.b64encode(buf).decode("utf-8")
            except Exception:
                logger.warning("Failed to encode screenshot for intervention")

        node_name = current_node.cn if current_node else None

        # Pause the app
        try:
            if hasattr(z_ctx, "run_context"):
                z_ctx.run_context.switch_context_pause_and_run()
        except Exception:
            logger.warning("Failed to pause app during intervention")

        # Block until Agent resolves (or timeout)
        logger.info(f"Intervention requested: {reason}")
        resolution = intervention_queue.request(
            reason=reason,
            node_name=node_name,
            screenshot_base64=screenshot_b64,
        )
        logger.info(f"Intervention resolved: {resolution}")

        # Resume the app
        try:
            if hasattr(z_ctx, "run_context"):
                z_ctx.run_context.switch_context_pause_and_run()
        except Exception:
            logger.warning("Failed to resume app after intervention")

    operation_notify.send_node_notify = patched_notify
    logger.info("Monkey-patch applied to send_node_notify")
    return True
