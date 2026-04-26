"""
feature_flag_env/tools/mock_adapters.py

Mock tool implementations for training and testing.

These return simulated responses based on environment state
without making any real API calls.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from .tool_interface import Tool, ToolMode, ValidationResult


# ---------------------------------------------------------------------------
# MockGitHubTool
# ---------------------------------------------------------------------------

class MockGitHubTool(Tool):
    """
    Simulated GitHub integration.

    Actions:
        get_deployment_status — returns simulated deployment status correlated
                                with current rollout and error metrics
        get_cicd_status       — returns simulated CI/CD pipeline status
        create_rollout_pr     — simulates PR creation (always succeeds)
        get_latest_deployment — returns latest deployment info
    """

    def __init__(self, **kwargs):
        super().__init__(
            name="github",
            mode=ToolMode.MOCK,
            available_actions=[
                "get_deployment_status",
                "get_cicd_status",
                "create_rollout_pr",
                "get_latest_deployment",
            ],
            **kwargs,
        )
        self._env_state: Dict[str, Any] = {}

    def set_env_state(self, state: Dict[str, Any]) -> None:
        """Inject current environment state for realistic mock responses."""
        self._env_state = state

    def _execute(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action_name == "get_deployment_status":
            return self._mock_deployment_status(params)
        elif action_name == "get_cicd_status":
            return self._mock_cicd_status(params)
        elif action_name == "create_rollout_pr":
            return self._mock_create_pr(params)
        elif action_name == "get_latest_deployment":
            return self._mock_latest_deployment(params)
        return {}

    def validate(self, action_name: str, params: Dict[str, Any]) -> ValidationResult:
        base = super().validate(action_name, params)
        if not base.valid:
            return base

        errors = []
        if action_name == "create_rollout_pr":
            if "rollout_percentage" not in params:
                errors.append("Missing required param: rollout_percentage")
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    # -- mock generators -----------------------------------------------------

    def _mock_deployment_status(self, params: Dict) -> Dict:
        error_rate = self._env_state.get("error_rate", 0.02)
        rollout = self._env_state.get("rollout_percentage", 0.0)

        if error_rate > 0.10:
            status = "failure"
        elif error_rate > 0.05:
            status = "error"
        elif rollout >= 100:
            status = "success"
        else:
            status = "in_progress"

        return {
            "environment": params.get("environment", "production"),
            "status": status,
            "deployments": [
                {
                    "id": random.randint(1000, 9999),
                    "sha": f"abc{random.randint(1000,9999)}",
                    "status": status,
                    "rollout_pct": rollout,
                }
            ],
            "total_checked": 1,
        }

    def _mock_cicd_status(self, params: Dict) -> Dict:
        error_rate = self._env_state.get("error_rate", 0.02)
        # Higher error rate → more failed pipelines
        fail_prob = min(error_rate * 5, 0.8)
        runs = []
        for i in range(3):
            conclusion = "failure" if random.random() < fail_prob else "success"
            runs.append({
                "workflow_name": f"pipeline-{i+1}",
                "status": "completed",
                "conclusion": conclusion,
            })

        successful = sum(1 for r in runs if r["conclusion"] == "success")
        return {
            "branch": params.get("branch", "main"),
            "recent_runs": runs,
            "summary": {
                "total_checked": len(runs),
                "successful": successful,
                "failed": len(runs) - successful,
                "success_rate": (successful / len(runs) * 100) if runs else 0,
            },
        }

    def _mock_create_pr(self, params: Dict) -> Dict:
        return {
            "pr_number": random.randint(100, 999),
            "pr_url": f"https://github.com/mock/repo/pull/{random.randint(100,999)}",
            "title": f"Rollout to {params.get('rollout_percentage', 0)}%",
            "state": "open",
        }

    def _mock_latest_deployment(self, params: Dict) -> Dict:
        error_rate = self._env_state.get("error_rate", 0.02)
        return {
            "id": random.randint(1000, 9999),
            "environment": params.get("environment", "production"),
            "status": "success" if error_rate < 0.05 else "failure",
            "is_healthy": error_rate < 0.05,
        }


# ---------------------------------------------------------------------------
# MockSlackTool
# ---------------------------------------------------------------------------

class MockSlackTool(Tool):
    """
    Simulated Slack integration.

    Actions:
        send_message       — logs message (always succeeds)
        send_rollout_update — logs formatted update (always succeeds)
    """

    def __init__(self, **kwargs):
        super().__init__(
            name="slack",
            mode=ToolMode.MOCK,
            available_actions=[
                "send_message",
                "send_rollout_update",
            ],
            **kwargs,
        )
        self.message_log: List[Dict[str, Any]] = []

    def _execute(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action_name == "send_message":
            return self._mock_send_message(params)
        elif action_name == "send_rollout_update":
            return self._mock_send_rollout_update(params)
        return {}

    def validate(self, action_name: str, params: Dict[str, Any]) -> ValidationResult:
        base = super().validate(action_name, params)
        if not base.valid:
            return base

        errors = []
        if "channel" not in params:
            errors.append("Missing required param: channel")
        if action_name == "send_message" and "text" not in params:
            errors.append("Missing required param: text")
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def reset(self) -> None:
        super().reset()
        self.message_log.clear()

    def _mock_send_message(self, params: Dict) -> Dict:
        entry = {
            "channel": params["channel"],
            "text": params.get("text", ""),
            "type": "message",
        }
        self.message_log.append(entry)
        return {"ts": f"mock_{len(self.message_log)}", "channel": params["channel"]}

    def _mock_send_rollout_update(self, params: Dict) -> Dict:
        entry = {
            "channel": params["channel"],
            "feature_name": params.get("feature_name", "unknown"),
            "action": params.get("action", "MAINTAIN"),
            "percentage": params.get("percentage", 0),
            "type": "rollout_update",
        }
        self.message_log.append(entry)
        return {"ts": f"mock_{len(self.message_log)}", "channel": params["channel"]}
