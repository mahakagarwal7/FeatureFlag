import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Keep agent usable even if dotenv isn't installed.
    load_dotenv = None

from agents.llm_agent import LLMAgent
from agents.baseline_agent import BaselineAgent


if load_dotenv is not None:
    load_dotenv()
    project_env = Path(__file__).resolve().parents[1] / ".env"
    if project_env.exists():
        load_dotenv(dotenv_path=project_env)


class HybridAgent:
    def __init__(self):
        self.llm = LLMAgent()
        self.safe = BaselineAgent()
        self.debug = os.getenv("FF_DEBUG_API", "0") == "1"
        self.api_calls = 0
        self.safety_overrides = 0

    def decide(self, observation, history):
        proposed = self.llm.decide(observation, history)
        self.api_calls = self.llm.api_calls

        # safety override
        if proposed.action_type == "INCREASE_ROLLOUT" and observation.error_rate > 0.10:
            safe_action = self.safe.decide(observation, history)
            safe_action.reason = "Safety override"
            self.safety_overrides += 1
            if self.debug:
                print(
                    f"[HYBRID DEBUG] override#{self.safety_overrides} "
                    f"error={observation.error_rate * 100:.2f}%"
                )
            return safe_action

        if self.debug:
            print(
                f"[HYBRID DEBUG] pass-through action={proposed.action_type} "
                f"target={proposed.target_percentage} api_calls={self.api_calls}"
            )
        return proposed