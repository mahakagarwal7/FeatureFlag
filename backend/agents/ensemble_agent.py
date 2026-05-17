from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from agents.baseline_agent import BaselineAgent
from agents.llm_agent import LLMAgent
from agents.rl_agent import RLAgent
from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation

try:
    import torch
except ImportError:
    torch = None


VALID_STRATEGIES = {"weighted", "rl_with_safety", "majority", "confidence"}


@dataclass
class EnsembleDecision:
    winner: str
    action: FeatureFlagAction


class EnsembleAgent:
    """Multi-agent ensemble wrapper around RL, baseline, and LLM agents."""

    def __init__(
        self,
        task: str = "task1",
        model_path: str | None = None,
        strategy: str = "weighted",
        weights: Dict[str, float] | None = None,
    ):
        self.task = task
        self.strategy = (strategy or "weighted").strip().lower()
        if self.strategy not in VALID_STRATEGIES:
            raise ValueError(f"Unknown ensemble strategy: {self.strategy}")

        self.rl_agent = RLAgent(
            task=task,
            model_path=model_path,
            training=False,
            epsilon=0.0,
            epsilon_min=0.0,
        )
        self.rl_agent.epsilon = 0.0
        self.baseline_agent = BaselineAgent()
        self.llm_agent = LLMAgent()

        default_weights = {"rl": 0.5, "baseline": 0.3, "llm": 0.2}
        merged = {**default_weights, **(weights or {})}
        self.weights = self._normalize_weights(merged)

        self.total_decisions = 0
        self.agreement_count = 0
        self.wins = Counter({"rl": 0, "baseline": 0, "llm": 0})
        self.last_vote_actions: Dict[str, FeatureFlagAction] = {}

    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        filtered = {
            name: max(0.0, float(weights.get(name, 0.0)))
            for name in ("rl", "baseline", "llm")
        }
        total = sum(filtered.values())
        if total <= 0:
            return {"rl": 0.5, "baseline": 0.3, "llm": 0.2}
        return {name: value / total for name, value in filtered.items()}

    def _action_signature(self, action: FeatureFlagAction) -> Tuple[str, float]:
        return action.action_type, round(float(action.target_percentage), 1)

    def _collect_votes(self, observation: FeatureFlagObservation, history) -> Dict[str, FeatureFlagAction]:
        rl_action = self.rl_agent.decide(observation, history)
        baseline_action = self.baseline_agent.decide(observation, history)
        llm_action = self.llm_agent.decide(observation, history)
        votes = {"rl": rl_action, "baseline": baseline_action, "llm": llm_action}
        self.last_vote_actions = votes
        return votes

    def _is_unsafe(self, action: FeatureFlagAction, observation: FeatureFlagObservation) -> bool:
        if action.action_type in {"FULL_ROLLOUT", "INCREASE_ROLLOUT"}:
            if observation.error_rate > 0.10:
                return True
            if observation.system_health_score < 0.70:
                return True
            if action.target_percentage > observation.current_rollout_percentage + 20:
                return True
        if action.action_type == "FULL_ROLLOUT" and observation.error_rate > 0.05:
            return True
        return False

    def _confidence_rl(self, observation: FeatureFlagObservation) -> float:
        if torch is None:
            return 0.6
        state = self.rl_agent.encode_state(observation)
        with torch.no_grad():
            state_tensor = torch.from_numpy(state).float().unsqueeze(0).to(self.rl_agent.device)
            q_values = self.rl_agent.policy_net(state_tensor).cpu().numpy().reshape(-1)
        stabilized = q_values - np.max(q_values)
        probs = np.exp(stabilized)
        probs = probs / max(np.sum(probs), 1e-12)
        return float(np.max(probs))

    def _confidence_baseline(self, action: FeatureFlagAction, observation: FeatureFlagObservation) -> float:
        error = float(observation.error_rate)
        if action.action_type == "ROLLBACK" and error > 0.15:
            return 0.95
        if action.action_type == "DECREASE_ROLLOUT" and error > 0.07:
            return 0.85
        if action.action_type == "INCREASE_ROLLOUT" and error < 0.03:
            return 0.75
        if action.action_type == "MAINTAIN":
            return 0.65
        return 0.6

    def _confidence_llm(self) -> float:
        if self.llm_agent.use_baseline:
            return 0.55
        return 0.65

    def _pick_majority(self, votes: Dict[str, FeatureFlagAction]) -> EnsembleDecision:
        counts = Counter(v.action_type for v in votes.values())
        top_count = max(counts.values())
        top_actions = {k for k, v in counts.items() if v == top_count}
        for preferred in ("rl", "baseline", "llm"):
            if votes[preferred].action_type in top_actions:
                return EnsembleDecision(preferred, votes[preferred])
        return EnsembleDecision("rl", votes["rl"])

    def _pick_weighted(self, votes: Dict[str, FeatureFlagAction]) -> EnsembleDecision:
        action_scores: Dict[str, float] = defaultdict(float)
        for name, action in votes.items():
            action_scores[action.action_type] += self.weights[name]

        top_score = max(action_scores.values())
        top_actions = {action for action, score in action_scores.items() if score == top_score}
        for preferred in ("rl", "baseline", "llm"):
            if votes[preferred].action_type in top_actions:
                return EnsembleDecision(preferred, votes[preferred])
        return EnsembleDecision("rl", votes["rl"])

    def _pick_rl_with_safety(self, votes: Dict[str, FeatureFlagAction], observation: FeatureFlagObservation) -> EnsembleDecision:
        if self._is_unsafe(votes["rl"], observation):
            return EnsembleDecision("baseline", votes["baseline"])
        return EnsembleDecision("rl", votes["rl"])

    def _pick_confidence(self, votes: Dict[str, FeatureFlagAction], observation: FeatureFlagObservation) -> EnsembleDecision:
        scores = {
            "rl": self._confidence_rl(observation) * self.weights["rl"],
            "baseline": self._confidence_baseline(votes["baseline"], observation) * self.weights["baseline"],
            "llm": self._confidence_llm() * self.weights["llm"],
        }
        winner = max(scores, key=scores.get)
        return EnsembleDecision(winner, votes[winner])

    def _update_stats(self, votes: Dict[str, FeatureFlagAction], winner: str) -> None:
        self.total_decisions += 1
        self.wins[winner] += 1
        signatures = Counter(self._action_signature(action) for action in votes.values())
        if signatures and max(signatures.values()) >= 2:
            self.agreement_count += 1

    def decide(self, observation: FeatureFlagObservation, history):
        votes = self._collect_votes(observation, history)

        if self.strategy == "majority":
            result = self._pick_majority(votes)
        elif self.strategy == "rl_with_safety":
            result = self._pick_rl_with_safety(votes, observation)
        elif self.strategy == "confidence":
            result = self._pick_confidence(votes, observation)
        else:
            result = self._pick_weighted(votes)

        self._update_stats(votes, result.winner)
        vote_summary = ", ".join(
            f"{name}:{action.action_type}"
            for name, action in votes.items()
        )
        result.action.reason = (
            f"{result.action.reason} | ensemble(strategy={self.strategy}, winner={result.winner}, votes={vote_summary})"
        )
        return result.action

    def get_stats(self) -> Dict[str, float | int]:
        agreement_rate = 0.0
        if self.total_decisions > 0:
            agreement_rate = 100.0 * self.agreement_count / self.total_decisions
        return {
            "total_decisions": self.total_decisions,
            "agreement_rate": agreement_rate,
            "rl_wins": self.wins["rl"],
            "baseline_wins": self.wins["baseline"],
            "llm_wins": self.wins["llm"],
        }
