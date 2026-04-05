"""App dispatch MCP tools.

Calling existing framework automation modules — the Agent's "hands".
These tools start, stop, pause, and manage automation app execution.

TODO(codex): Implement all tool bodies. Key patterns:
  - Use asyncio.to_thread() to call sync framework methods
  - Push events to ctx.events on state changes
  - Check z_ctx.run_context._run_state before operations
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP) -> None:
    """Register all dispatch tools on the MCP server."""

    @mcp.tool()
    async def start_app(app_id: str, config: dict[str, Any] | None = None, instance_idx: int = 0) -> dict[str, Any]:
        """Start an automation app asynchronously.

        The app runs in the framework's thread pool. Monitor progress via
        get_app_status() or subscribe to events.

        Args:
            app_id: App identifier (e.g. "hollow_zero", "coffee", "scratch_card").
            config: Optional config overrides applied before launch.
            instance_idx: Game account instance index (default 0).

        Returns:
            {"started": true, "app_id": "hollow_zero"} on success,
            {"started": false, "reason": "another app is running"} on failure.

        TODO(codex): Implement.
        - Check run_context._run_state is STOP (no other app running)
        - If config provided: get_config(app_id) and apply overrides
        - Call run_context.run_application_async(app_id, instance_idx)
        - Push APP_STARTED event
        - Return result
        """
        raise NotImplementedError(f"start_app({app_id}) not yet implemented")

    @mcp.tool()
    async def stop_app() -> dict[str, Any]:
        """Stop the currently running app.

        Returns:
            {"stopped": true} if an app was running,
            {"stopped": false, "reason": "no app running"} otherwise.

        TODO(codex): Implement.
        - Call run_context.stop_running()
        - Push APP_STOPPED event
        """
        raise NotImplementedError("stop_app not yet implemented")

    @mcp.tool()
    async def pause_app() -> dict[str, Any]:
        """Pause the currently running app.

        Useful when the Agent needs to inspect state mid-execution.
        Resume with resume_app().

        Returns:
            {"paused": true} or {"paused": false, "reason": "..."}.

        TODO(codex): Implement.
        - Check run_context._run_state is RUNNING
        - Call run_context.pause_resume() (toggles pause)
        """
        raise NotImplementedError("pause_app not yet implemented")

    @mcp.tool()
    async def resume_app() -> dict[str, Any]:
        """Resume a paused app.

        Returns:
            {"resumed": true} or {"resumed": false, "reason": "..."}.

        TODO(codex): Implement.
        - Check run_context._run_state is PAUSE
        - Call run_context.pause_resume() (toggles to running)
        """
        raise NotImplementedError("resume_app not yet implemented")

    @mcp.tool()
    async def retry_app(app_id: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Stop current app (if running), apply new config, and restart.

        Used when the Agent decides to try a different strategy after failure.

        Args:
            app_id: App to retry.
            config: New config overrides for this attempt.

        Returns:
            Same as start_app().

        TODO(codex): Implement.
        - stop_app() if running
        - Short delay for cleanup
        - start_app(app_id, config)
        """
        raise NotImplementedError(f"retry_app({app_id}) not yet implemented")

    @mcp.tool()
    async def switch_instance(instance_idx: int) -> dict[str, Any]:
        """Switch to a different game account/instance.

        Reloads all instance-specific configs (characters, settings, etc.).

        Args:
            instance_idx: Instance index to switch to.

        Returns:
            {"switched": true, "instance_idx": 1}

        TODO(codex): Implement.
        - Call z_ctx.switch_instance(instance_idx)
        - Reload instance configs
        """
        raise NotImplementedError(f"switch_instance({instance_idx}) not yet implemented")

    @mcp.tool()
    async def list_instances() -> list[dict[str, Any]]:
        """List all configured game account instances.

        Returns:
            [{"idx": 0, "name": "Account 1", "active": true}, ...]

        TODO(codex): Implement.
        - Read z_ctx.one_dragon_config.instance_list
        - Mark currently active instance
        """
        raise NotImplementedError("list_instances not yet implemented")
