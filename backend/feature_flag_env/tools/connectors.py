"""
feature_flag_env/tools/connectors.py

Connector Framework Extension.
Provides low-level network/API abstraction (Connectors) which can be optionally dynamically wrapped
by higher-level lifecycle handlers (Tools) to enforce backward compatibility and tracking.
"""

import os
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class ToolResult(BaseModel):
    """Standardized result from any tool call."""
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class Connector(ABC):
    """
    Abstract Base Class for pure data-fetching and action-dispatching integrations.
    Unlike Tools, Connectors do not track per-episode metrics, maintain local error limits,
    or validate high-level environment actions. They purely connect to APIs.
    """

    def __init__(self, name: str, base_url: str, api_key: Optional[str] = None):
        self.name = name
        self.base_url = base_url
        self.api_key = api_key
        self.is_connected = False

    def connect(self) -> bool:
        """Establish/Verify authentication to the external system."""
        # Simple simulated auth check
        self.is_connected = bool(self.api_key)
        return self.is_connected

    @abstractmethod
    def fetch_data(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Fetch observational metrics/configuration from the system."""
        pass

    @abstractmethod
    def send_action(self, endpoint: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        """Mutate state in the remote system."""
        pass


class GitHubClient:
    """GitHub integration for monitoring deployments."""
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")

    def get_deployment_status(self, limit: int = 1) -> ToolResult:
        """Fetch recent deployments from GitHub API."""
        if not self.token:
            return ToolResult(success=False, error="GitHub token not configured")
        
        owner = os.getenv("GITHUB_OWNER", "your-org")
        repo = os.getenv("GITHUB_REPO", "your-repo")
        url = f"https://api.github.com/repos/{owner}/{repo}/deployments"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        
        try:
            response = requests.get(
                url,
                headers=headers,
                params={"per_page": limit},
                timeout=int(os.getenv("GITHUB_TIMEOUT_SECONDS", "10")),
            )
            response.raise_for_status()
            deployments = response.json()
            
            # Transform to expected format
            formatted = [
                {
                    "id": d["id"],
                    "sha": d["sha"],
                    "status": d.get("state", "unknown"),  # GitHub uses 'state'
                    "environment": d.get("environment"),
                    "created_at": d.get("created_at"),
                }
                for d in deployments[:limit]
            ]
            
            return ToolResult(success=True, data={"deployments": formatted})
            
        except requests.exceptions.RequestException as e:
            return ToolResult(success=False, error=f"GitHub API error: {str(e)}")


class SlackClient:
    """Slack integration to send notifications."""
    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("SLACK_BOT_TOKEN")

    def send_rollout_update(
        self,
        channel: str,
        feature_name: str,
        action: str,
        percentage: float,
        metrics: dict,
        reasoning: str,
    ) -> ToolResult:
        """Send rollout update to Slack channel."""
        if not self.bot_token:
            return ToolResult(success=False, error="Slack bot token not configured")
        
        url = "https://slack.com/api/chat.postMessage"
        headers = {"Authorization": f"Bearer {self.bot_token}"}
        
        # Build rich message blocks
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🚀 Feature Rollout Update: {feature_name}"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Action:*\n{action}"},
                    {"type": "mrkdwn", "text": f"*Target:*\n{percentage:.1f}%"},
                    {"type": "mrkdwn", "text": f"*Error Rate:*\n{metrics.get('error_rate', 'N/A')}"},
                    {"type": "mrkdwn", "text": f"*Latency:*\n{metrics.get('latency', 'N/A')}"},
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Reasoning:*\n{reasoning}"}
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f" Sent by FeatureFlag Agent • {datetime.utcnow().isoformat()}"}]
            }
        ]
        
        payload = {
            "channel": channel,
            "blocks": blocks,
            "text": f"Rollout update for {feature_name}: {action} to {percentage:.1f}%",  # Fallback text
        }
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=int(os.getenv("SLACK_TIMEOUT_SECONDS", "10")),
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("ok"):
                return ToolResult(success=True, data={"ts": result["ts"], "channel": result["channel"]})
            else:
                return ToolResult(success=False, error=f"Slack API error: {result.get('error')}")
                
        except requests.exceptions.RequestException as e:
            return ToolResult(success=False, error=f"Slack request failed: {str(e)}")


# --- Registry ---

class ConnectorRegistry:
    """Manages low-level Connectors."""
    def __init__(self):
        self._connectors: Dict[str, Connector] = {}

    def register(self, connector: Connector):
        self._connectors[connector.name] = connector

    def get_connector(self, name: str) -> Optional[Connector]:
        return self._connectors.get(name)

    def list_connectors(self) -> list[str]:
        return list(self._connectors.keys())
