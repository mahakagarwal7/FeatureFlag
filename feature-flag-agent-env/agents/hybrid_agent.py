from agents.llm_agent import LLMAgent
from agents.baseline_agent import BaselineAgent


class HybridAgent:
    def __init__(self):
        self.llm = LLMAgent()
        self.safe = BaselineAgent()

    def decide(self, observation, history):
        proposed = self.llm.decide(observation, history)

        # safety override
        if proposed.action_type == "INCREASE_ROLLOUT" and observation.error_rate > 0.10:
            safe_action = self.safe.decide(observation, history)
            safe_action.reason = "Safety override"
            return safe_action

        return proposed