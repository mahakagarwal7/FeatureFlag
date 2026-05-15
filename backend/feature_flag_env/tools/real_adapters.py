"""
feature_flag_env/tools/real_adapters.py

Real tool adapters that wrap the existing API clients
(GitHubClient, SlackClient) behind the
unified Tool interface.

For production use when the agent should interact with
actual external services.
"""

from __future__ import annotations

from typing import Any, Dict

from .tool_interface import Tool, ToolMode, ValidationResult
from .base_tools import ToolStatus


# ---------------------------------------------------------------------------
# RealGitHubTool
# ---------------------------------------------------------------------------

class RealGitHubTool(Tool):
    """
    Wraps existing GitHubClient behind the unified Tool interface.

    Usage:
        from feature_flag_env.tools.github_integration import GitHubClient
        client = GitHubClient(token="...", repo="owner/repo")
        client.authenticate()
        tool = RealGitHubTool(client)
    """

    def __init__(self, client=None, **kwargs):
        super().__init__(
            name="github",
            mode=ToolMode.REAL,
            available_actions=[
                "get_deployment_status",
                "get_cicd_status",
                "create_rollout_pr",
                "get_latest_deployment",
            ],
            timeout_ms=10000.0,
            **kwargs,
        )
        self._client = client  # GitHubClient instance

    def set_client(self, client) -> None:
        self._client = client

    def _execute(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._client is None:
            raise RuntimeError("GitHubClient not set. Call set_client() first.")
        if self._client.status != ToolStatus.CONNECTED:
            raise RuntimeError("GitHubClient not authenticated. Call client.authenticate().")

        if action_name == "get_deployment_status":
            resp = self._client.get_deployment_status(
                environment=params.get("environment", "production"),
                limit=params.get("limit", 5),
            )
        elif action_name == "get_cicd_status":
            resp = self._client.get_cicd_pipeline_status(
                branch=params.get("branch", "main"),
                limit=params.get("limit", 10),
            )
        elif action_name == "create_rollout_pr":
            resp = self._client.create_rollout_pr(
                feature_branch=params.get("feature_branch", "feature/rollout"),
                target_branch=params.get("target_branch", "main"),
                rollout_percentage=params.get("rollout_percentage", 0),
                title=params.get("title"),
                description=params.get("description"),
                labels=params.get("labels"),
            )
        elif action_name == "get_latest_deployment":
            resp = self._client.get_latest_deployment(
                environment=params.get("environment", "production"),
            )
        else:
            raise ValueError(f"Unknown action: {action_name}")

        if not resp.success:
            raise RuntimeError(resp.error or "GitHub API call failed")
        return resp.data or {}

    def validate(self, action_name: str, params: Dict[str, Any]) -> ValidationResult:
        base = super().validate(action_name, params)
        if not base.valid:
            return base

        errors = []
        if action_name == "create_rollout_pr":
            if "rollout_percentage" not in params:
                errors.append("Missing required param: rollout_percentage")
        if self._client is None:
            errors.append("GitHubClient not configured")
        return ValidationResult(valid=len(errors) == 0, errors=errors)


# ---------------------------------------------------------------------------
# RealSlackTool
# ---------------------------------------------------------------------------

class RealSlackTool(Tool):
    """
    Wraps existing SlackClient behind the unified Tool interface.

    Usage:
        from feature_flag_env.tools.slack_integration import SlackClient
        client = SlackClient()
        client.authenticate()
        tool = RealSlackTool(client)
    """

    def __init__(self, client=None, **kwargs):
        super().__init__(
            name="slack",
            mode=ToolMode.REAL,
            available_actions=[
                "send_message",
                "send_rollout_update",
            ],
            timeout_ms=5000.0,
            **kwargs,
        )
        self._client = client

    def set_client(self, client) -> None:
        self._client = client

    def _execute(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._client is None:
            raise RuntimeError("SlackClient not set.")
        if self._client.status != ToolStatus.CONNECTED:
            raise RuntimeError("SlackClient not authenticated.")

        if action_name == "send_message":
            resp = self._client.send_message(
                channel=params["channel"],
                text=params.get("text", ""),
                blocks=params.get("blocks"),
            )
        elif action_name == "send_rollout_update":
            resp = self._client.send_rollout_update(
                channel=params["channel"],
                feature_name=params.get("feature_name", "unknown"),
                action=params.get("action", "MAINTAIN"),
                percentage=params.get("percentage", 0),
                metrics=params.get("metrics", {}),
                reasoning=params.get("reasoning", ""),
            )
        else:
            raise ValueError(f"Unknown action: {action_name}")

        if not resp.success:
            raise RuntimeError(resp.error or "Slack API call failed")
        return resp.data or {}

    def validate(self, action_name: str, params: Dict[str, Any]) -> ValidationResult:
        base = super().validate(action_name, params)
        if not base.valid:
            return base

        errors = []
        if "channel" not in params:
            errors.append("Missing required param: channel")
        if action_name == "send_message" and "text" not in params:
            errors.append("Missing required param: text")
        if self._client is None:
            errors.append("SlackClient not configured")
        return ValidationResult(valid=len(errors) == 0, errors=errors)
