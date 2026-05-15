import os
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

from agents.llm_agent import LLMAgent
from feature_flag_env.models import FeatureFlagObservation, FeatureFlagAction
from feature_flag_env.tools.github_integration import GitHubClient
from feature_flag_env.tools.slack_integration import SlackClient

class MasterAgent(LLMAgent):
    """
    The ultimate Feature Flag Agent.
    
    Combines:
    - LLM Decision Making
    - GitHub Deployment & Pipeline Awareness
    - Slack Notifications
    """
    
    def __init__(self, model: str = ""):
        super().__init__(model=model)
        
        # Initialize Tools
        self.github = GitHubClient()
        self.slack = SlackClient()
        
        # Authenticate Tools (failures are handled gracefully)
        self.github_auth = self.github.authenticate()
        self.slack_auth = self.slack.authenticate()
        
        # Slack Channel auto-discovery
        self.slack_channel = os.getenv("SLACK_CHANNEL")
        if not self.slack_channel and self.slack_auth.success:
            joined = self.slack.find_joined_channels()
            if joined:
                self.slack_channel = joined[0]["id"]
                print(f"[MasterAgent] Auto-discovered Slack channel: {joined[0]['name']} ({self.slack_channel})")
            else:
                print("[MasterAgent] WARNING: No Slack channel discovered and SLACK_CHANNEL not set.")
                
        self.service_name = os.getenv("GITHUB_REPO", "unknown-service")
        
    def _fetch_external_context(self) -> str:
        """Fetch context from GitHub to feed into LLM."""
        context = "\n--- EXTERNAL CONTEXT ---\n"
        
        # GitHub Context
        if self.github_auth.success:
            deploy = self.github.get_deployment_status(limit=1)
            pipeline = self.github.get_cicd_pipeline_status(limit=1)
            
            if deploy.success and deploy.data["deployments"]:
                latest = deploy.data["deployments"][0]
                context += f"GitHub Deployment: {latest['status']} (SHA: {latest['sha']})\n"
            
            if pipeline.success:
                summary = pipeline.data["summary"]
                context += f"GitHub Pipeline: {summary['success_rate']:.1f}% success rate\n"
        else:
            context += "GitHub: Not connected\n"
            
        return context

    def decide(self, observation: FeatureFlagObservation, history) -> FeatureFlagAction:
        """
        Decision process:
        1. Fetch external context.
        2. Combine with simulation observation.
        3. Let LLM decide.
        4. Notify Slack on important changes.
        """
        # Step 1: External Context
        external_context = self._fetch_external_context()
        print(f"\n[MasterAgent] Fetched External Context:{external_context}")
        
        # Step 2: Get Decision from LLM (injecting external context into prompt)
        # We wrap the original decide method logic or just call it with modified prompt
        # For simplicity, we'll append external context to the prompt
        
        original_prompt_method = self._get_prompt if hasattr(self, "_get_prompt") else None
        
        # If we can't easily modify the prompt in LLMAgent, we'll reimplement the call here
        # but use LLMAgent's helper methods.
        
        action = self._decide_with_context(observation, history, external_context)
        
        # Step 3: Slack Notification
        self._notify_slack(observation, action)
        
        return action

    def _decide_with_context(self, observation, history, external_context) -> FeatureFlagAction:
        """Modified LLM decision with external context."""
        if self.use_baseline:
            return self._fallback(observation, history)

        try:
            prompt = f"""
{external_context}

Simulation Observation:
- Feature: {observation.feature_name}
- Step: {observation.time_step}
- Rollout: {observation.current_rollout_percentage:.1f}%
- Error Rate: {observation.error_rate*100:.2f}%
- Latency: {observation.latency_p99_ms:.1f}ms
- System Health: {observation.system_health_score:.2f}
- Active Users: {observation.active_users}

Based on the above EXTERNAL CONTEXT and Simulation facts, make a rollout decision.
Priority: 
1. If External Pipeline is failing, be EXTREMELY conservative (Maintain or Decrease).
2. If metrics are healthy, aim for steady rollout.

Allowed action_type: INCREASE_ROLLOUT, DECREASE_ROLLOUT, MAINTAIN, HALT_ROLLOUT, FULL_ROLLOUT, ROLLBACK

Respond with JSON:
{{
  "action_type": "...",
  "target_percentage": number,
  "reason": "..."
}}
"""
            # Call LLMAgent's internal logic if possible, or just call OpenAI here
            # Since LLMAgent.decide doesn't take a prompt, we have to replicate the API call
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an advanced rollout controller with DevOps awareness."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3, # lower temperature for more consistent decisions
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content
            data = self._parse_llm_json(content)
            normalized_action = self._normalize_action_type(data.get("action_type"))
            target_percentage = self._resolve_target_percentage(
                data.get("target_percentage"),
                normalized_action,
                observation.current_rollout_percentage,
            )
            reason = data.get("reason") or "MasterAgent Decision"
            
            return FeatureFlagAction(
                action_type=normalized_action,
                target_percentage=target_percentage,
                reason=reason
            )

        except Exception as e:
            print(f"MasterAgent LLM Error: {e}")
            return self._fallback(observation, history)

    def _notify_slack(self, observation: FeatureFlagObservation, action: FeatureFlagAction):
        """Send update to slack if it's a significant change."""
        if not self.slack_auth.success:
            return

        # Only notify on changes or errors
        if action.action_type != "MAINTAIN" or observation.error_rate > 0.05:
            self.slack.send_rollout_update(
                channel=self.slack_channel,
                feature_name=self.service_name,
                action=action.action_type,
                percentage=action.target_percentage,
                metrics={
                    "error_rate": f"{observation.error_rate*100:.2f}%",
                    "latency": f"{observation.latency_p99_ms:.0f}"
                },
                reasoning=action.reason
            )
