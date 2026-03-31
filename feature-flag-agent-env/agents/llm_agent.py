import os
import json
from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation


class LLMAgent:
    def __init__(self, model: str = "llama-3.1-8b-instant"):
        self.model = model
        self.api_key = os.getenv("GROQ_API_KEY")

        if not self.api_key:
            print("⚠️  GROQ_API_KEY not set. Using fallback.")
            self.use_baseline = True
        else:
            self.use_baseline = False
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
            except ImportError:
                print("⚠️ groq not installed. Using fallback.")
                self.use_baseline = True

    def _fallback(self, observation, history):
        from agents.baseline_agent import BaselineAgent
        return BaselineAgent().decide(observation, history)

    def decide(self, observation: FeatureFlagObservation, history):
        if self.use_baseline:
            return self._fallback(observation, history)

        try:
            prompt = f"""
Feature rollout decision:

Rollout: {observation.current_rollout_percentage}%
Error: {observation.error_rate*100:.2f}%
Latency: {observation.latency_p99_ms}
Adoption: {observation.user_adoption_rate}
Revenue: {observation.revenue_impact}
Health: {observation.system_health_score}

Respond JSON:
{{
 "action_type": "...",
 "target_percentage": number
}}
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
            )

            data = json.loads(response.choices[0].message.content)

            return FeatureFlagAction(
                action_type=data["action_type"],
                target_percentage=data["target_percentage"],
                reason="LLM decision"
            )

        except Exception:
            return self._fallback(observation, history)