"""
feature_flag_env/tools/slack_integration.py

Slack Integration for Feature Flag Agents

Capabilities:
- Post simple messages and alerts to a channel
- Post beautifully formatted Block Kit messages summarizing rollout decisions
- Alert on degradation

Install: pip install slack_sdk

Usage:
    client = SlackClient()
    auth_response = client.authenticate()
    client.send_rollout_update(
        channel="#deployments",
        feature_name="checkout-v2",
        action="INCREASE_ROLLOUT",
        percentage=40,
        metrics={"error_rate": 0.01, "latency": 150}
    )
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from .base_tools import ExternalToolsInterface, ToolResponse, ToolStatus

class SlackClient(ExternalToolsInterface):
    """
    Slack integration to send notifications and updates.
    
    Requires SLACK_BOT_TOKEN to be exposed in environment.
    """
    
    def __init__(self, token: Optional[str] = None):
        super().__init__("slack")
        
        if load_dotenv is not None:
            env_candidates = [
                Path.cwd() / ".env",
                Path(__file__).resolve().parents[2] / ".env",
                Path(__file__).resolve().parents[3] / ".env",
            ]
            for env_path in env_candidates:
                if env_path.exists():
                    load_dotenv(dotenv_path=env_path)
                    
        self.token = token or os.getenv("SLACK_BOT_TOKEN")
        self.client = None
        
    def authenticate(self) -> ToolResponse:
        """Authenticate with Slack using auth.test."""
        try:
            if not self.token:
                error = "SLACK_BOT_TOKEN not provided or set in environment"
                self.status = ToolStatus.ERROR
                self._record_call(False, error)
                return ToolResponse(success=False, error=error)
                
            try:
                from slack_sdk import WebClient
                from slack_sdk.errors import SlackApiError
            except ImportError:
                error = "slack_sdk not installed. Run: pip install slack_sdk"
                self.status = ToolStatus.ERROR
                self._record_call(False, error)
                return ToolResponse(success=False, error=error)
            
            self.client = WebClient(token=self.token)
            
            # Verify token valid
            res = self.client.auth_test()
            
            self.status = ToolStatus.CONNECTED
            self._record_call(True)
            return ToolResponse(
                success=True,
                data={
                    "bot_id": res["bot_id"],
                    "team": res["team"],
                    "user": res["user"]
                },
                metadata={"message": "Successfully authenticated with Slack"}
            )
            
        except Exception as e:
            error = f"Slack authentication failed: {str(e)}"
            self.status = ToolStatus.ERROR
            self._record_call(False, error)
            return ToolResponse(success=False, error=error)

    def get_status(self) -> ToolStatus:
        return self.status

    def find_joined_channels(self) -> List[Dict[str, str]]:
        """Find channels the bot is already a member of."""
        try:
            if self.status != ToolStatus.CONNECTED:
                return []
                
            response = self.client.conversations_list(
                types="public_channel,private_channel",
                limit=100
            )
            
            joined_channels = []
            for channel in response["channels"]:
                if channel.get("is_member", False):
                    joined_channels.append({
                        "id": channel["id"],
                        "name": channel["name"]
                    })
            return joined_channels
        except Exception as e:
            print(f"Error finding joined channels: {e}")
            return []

    def send_message(self, channel: str, text: str, blocks: Optional[List[Dict]] = None) -> ToolResponse:
        """
        Send a generic message to a channel.
        Optionally uses Block Kit structure.
        """
        try:
            if self.status != ToolStatus.CONNECTED:
                return ToolResponse(success=False, error="Not authenticated.")
                
            from slack_sdk.errors import SlackApiError
            
            kwargs = {"channel": channel, "text": text}
            if blocks:
                kwargs["blocks"] = blocks
                
            response = self.client.chat_postMessage(**kwargs)
            self._record_call(True)
            
            return ToolResponse(
                success=True,
                data={"ts": response["ts"], "channel": response["channel"]},
                metadata={"timestamp": datetime.utcnow().isoformat()}
            )
        except Exception as e:
            error = f"Failed to send Slack message: {str(e)}"
            self._record_call(False, error)
            return ToolResponse(success=False, error=error)

    def send_rollout_update(
        self, 
        channel: str, 
        feature_name: str, 
        action: str, 
        percentage: float, 
        metrics: Dict[str, Any],
        reasoning: str = ""
    ) -> ToolResponse:
        """
        Sends a beautifully formatted Slack Block Kit alert when the agent makes a rollout decision.
        """
        
        # Color & Emoji coding
        emoji = "🔄"
        color_text = "Maintained"
        if action == "INCREASE_ROLLOUT":
            emoji = "🚀"
            color_text = "Increased"
        elif action == "DECREASE_ROLLOUT" or action == "ROLLBACK":
            emoji = "⚠️"
            color_text = "Decreased/Rollback"
        elif action == "FULL_ROLLOUT":
            emoji = "🎉"
            color_text = "100% Fully Deployed"
        elif action == "HALT_ROLLOUT":
            emoji = "🛑"
            color_text = "Halted"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} AIAgent Rollout Update: {feature_name}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Action Taken:* {color_text}\n*New Rollout Target:* `{percentage}%`"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Error Rate:*\n{metrics.get('error_rate', 'N/A')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Latency (p99):*\n{metrics.get('latency', 'N/A')}ms"
                    }
                ]
            }
        ]
        
        if reasoning:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"🤖 *Agent Reasoning:* {reasoning}"
                    }
                ]
            })

        fallback_text = f"Rollout Update: {feature_name} -> {percentage}%"
        return self.send_message(channel, text=fallback_text, blocks=blocks)