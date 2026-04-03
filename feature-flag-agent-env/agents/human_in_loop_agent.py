import os
import sys
from typing import List, Tuple

import numpy as np

from agents.baseline_agent import BaselineAgent
from agents.rl_agent import RLAgent
from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation

try:
    import torch
except ImportError:
    torch = None


class HumanInLoopAgent:
    """Human-in-the-loop wrapper around RL suggestions.

    Workflow:
    1. RL proposes an action and confidence.
    2. If confidence >= threshold, auto-approve.
    3. If confidence < threshold, ask human for approval/override.
    """

    def __init__(
        self,
        task: str = "task1",
        model_path: str | None = None,
        confidence_threshold: float = 0.75,
        non_interactive_action: str = "baseline",
        allow_human_prompt: bool = True,
    ):
        self.task = task
        self.confidence_threshold = max(0.0, min(1.0, float(confidence_threshold)))
        self.non_interactive_action = (non_interactive_action or "baseline").strip().lower()
        self.allow_human_prompt = allow_human_prompt
        self.debug = os.getenv("FF_DEBUG_DECISIONS", "0") == "1"

        self.rl_agent = RLAgent(
            task=task,
            model_path=model_path,
            training=False,
            epsilon=0.0,
            epsilon_min=0.0,
        )
        self.rl_agent.epsilon = 0.0
        self.baseline_agent = BaselineAgent()

    def _is_interactive(self) -> bool:
        if not self.allow_human_prompt:
            return False
        return bool(sys.stdin.isatty() and sys.stdout.isatty())

    def _allowed_actions(self, observation: FeatureFlagObservation) -> List[int]:
        allowed = list(range(self.rl_agent.action_dim))
        if self.task == "task1" and hasattr(self.rl_agent, "_task1_allowed_actions"):
            allowed = self.rl_agent._task1_allowed_actions(observation)
        elif self.task == "task2" and hasattr(self.rl_agent, "_task2_allowed_actions"):
            allowed = self.rl_agent._task2_allowed_actions(observation)
        return allowed or list(range(self.rl_agent.action_dim))

    def _rl_suggest_action(self, observation: FeatureFlagObservation) -> Tuple[FeatureFlagAction, float]:
        if torch is None:
            action = self.rl_agent.decide(observation, history=[])
            return action, 0.5

        state = self.rl_agent.encode_state(observation)
        allowed = self._allowed_actions(observation)

        with torch.no_grad():
            state_tensor = torch.from_numpy(state).float().unsqueeze(0).to(self.rl_agent.device)
            q_values = self.rl_agent.policy_net(state_tensor).cpu().numpy().reshape(-1)

        masked_q = q_values.copy()
        blocked = [idx for idx in range(self.rl_agent.action_dim) if idx not in allowed]
        if blocked:
            masked_q[blocked] = -1e9
        action_idx = int(np.argmax(masked_q))

        allowed_q = np.array([q_values[idx] for idx in allowed], dtype=np.float64)
        stabilized = allowed_q - np.max(allowed_q)
        probs = np.exp(stabilized)
        probs = probs / max(np.sum(probs), 1e-12)
        allowed_index = allowed.index(action_idx)
        confidence = float(probs[allowed_index])

        action = self.rl_agent._action_to_env(action_idx, observation)
        action.reason = (
            f"RL suggestion (confidence={confidence:.2f}, threshold={self.confidence_threshold:.2f})"
        )
        return action, confidence

    def _build_custom_action(self, current_rollout: float, target_percentage: float) -> FeatureFlagAction:
        target = max(0.0, min(100.0, target_percentage))
        if target > current_rollout:
            action_type = "INCREASE_ROLLOUT"
        elif target < current_rollout:
            action_type = "DECREASE_ROLLOUT"
        else:
            action_type = "MAINTAIN"
        return FeatureFlagAction(
            action_type=action_type,
            target_percentage=target,
            reason="Human override: custom rollout target",
        )

    def _resolve_low_confidence(
        self,
        observation: FeatureFlagObservation,
        history,
        suggested_action: FeatureFlagAction,
        confidence: float,
    ) -> FeatureFlagAction:
        if not self._is_interactive():
            if self.non_interactive_action == "approve":
                suggested_action.reason += " | auto-approved (non-interactive mode)"
                return suggested_action
            fallback = self.baseline_agent.decide(observation, history)
            fallback.reason = (
                f"Low RL confidence ({confidence:.2f}) and non-interactive mode; using baseline"
            )
            return fallback

        print("\n⚠️  HUMAN APPROVAL REQUIRED")
        print("=" * 58)
        print(
            "🤖 RL Suggestion: "
            f"{suggested_action.action_type} -> {suggested_action.target_percentage:.1f}%"
        )
        print(f"📊 Confidence: {confidence:.2f} (threshold: {self.confidence_threshold:.2f})")
        print("📝 Current State:")
        print(f"   - Rollout: {observation.current_rollout_percentage:.1f}%")
        print(f"   - Errors: {observation.error_rate * 100:.2f}%")
        print(f"   - Health: {observation.system_health_score:.2f}")
        print("=" * 58)
        print("Options:")
        print("   [y] Approve RL suggestion")
        print("   [n] Reject -> Use safe MAINTAIN action")
        print("   [b] Use Baseline agent instead")
        print("   [c] Custom percentage (enter value)")
        print("   [s] Skip episode")
        print("=" * 58)

        while True:
            choice = input("Your decision (y/n/b/c/s): ").strip().lower()
            if choice in {"y", "approve"}:
                suggested_action.reason += " | human-approved"
                return suggested_action
            if choice in {"n", "reject"}:
                return FeatureFlagAction(
                    action_type="MAINTAIN",
                    target_percentage=observation.current_rollout_percentage,
                    reason="Human rejected RL recommendation",
                )
            if choice in {"b", "baseline"}:
                baseline = self.baseline_agent.decide(observation, history)
                baseline.reason = f"Human selected baseline policy | {baseline.reason}"
                return baseline
            if choice in {"c", "custom"}:
                raw_target = input("Enter custom target percentage (0-100): ").strip()
                try:
                    target = float(raw_target)
                except ValueError:
                    print("Invalid number, try again.")
                    continue
                return self._build_custom_action(observation.current_rollout_percentage, target)
            if choice in {"s", "skip"}:
                return FeatureFlagAction(
                    action_type="MAINTAIN",
                    target_percentage=observation.current_rollout_percentage,
                    reason="Human requested episode skip; applying safe maintain action",
                )

            print("Invalid choice, please enter y/n/b/c/s.")

    def decide(self, observation: FeatureFlagObservation, history):
        suggested_action, confidence = self._rl_suggest_action(observation)

        if self.debug:
            print(
                "[HITL DEBUG] "
                f"suggested={suggested_action.action_type} "
                f"target={suggested_action.target_percentage:.1f}% "
                f"confidence={confidence:.2f} threshold={self.confidence_threshold:.2f}"
            )

        if confidence >= self.confidence_threshold:
            print(f"✅ Auto-approved: {suggested_action.action_type} (confidence={confidence:.2f})")
            suggested_action.reason += " | auto-approved"
            return suggested_action

        return self._resolve_low_confidence(observation, history, suggested_action, confidence)
