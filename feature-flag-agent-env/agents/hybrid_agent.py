import os
import sys
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

    def _is_unsafe(self, proposed, observation):
        if proposed.action_type in {"FULL_ROLLOUT", "INCREASE_ROLLOUT"}:
            if observation.error_rate > 0.10:
                return True
            if observation.system_health_score < 0.70:
                return True
            if proposed.target_percentage > observation.current_rollout_percentage + 20:
                return True

        if proposed.action_type == "FULL_ROLLOUT" and observation.error_rate > 0.05:
            return True

        return False

    def decide(self, observation, history):
        proposed = self.llm.decide(observation, history)
        self.api_calls = self.llm.api_calls
        safe_action = self.safe.decide(observation, history)

        if self._is_unsafe(proposed, observation):
            safe_action.reason = (
                f"Safety override: {proposed.reason or 'LLM action was unsafe'}"
            )
            self.safety_overrides += 1
            if self.debug:
                print(
                    f"[HYBRID DEBUG] override#{self.safety_overrides} "
                    f"proposed={proposed.action_type}({proposed.target_percentage}) "
                    f"error={observation.error_rate*100:.2f}% "
                    f"health={observation.system_health_score:.2f}",
                    file=sys.stderr,
                )
            return safe_action

        if self.debug:
            print(
                f"[HYBRID DEBUG] pass-through action={proposed.action_type} "
                f"target={proposed.target_percentage} api_calls={self.api_calls}",
                file=sys.stderr,
            )
        return proposed