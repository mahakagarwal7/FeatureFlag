"""
feature_flag_env/utils/extended_rewards.py

Extended reward components that stack on top of the base calculate_reward().

Components:
- stakeholder_satisfaction_reward: signal from stakeholder panel sentiment
- milestone_reward: bonus for completing a mission phase
- phase_progress_reward: incremental reward for progress within a phase
- tool_usage_reward: placeholder for future tool-usage incentives

Usage:
    calculate_extended_reward(
        old_obs, new_obs, action,
        stakeholder_sentiments={"devops": 0.7, "product": 0.5, "customer_success": 0.6},
        phase_advanced=False,
        phase_progress=0.3,
        phase_reward_weight=1.0,
    )
"""

from __future__ import annotations

import os
from typing import Dict, Optional

from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation
from feature_flag_env.utils.reward_functions import calculate_reward


# ---------------------------------------------------------------------------
# Individual reward components
# ---------------------------------------------------------------------------

def stakeholder_satisfaction_reward(
    feedback_vector: Dict[str, float],
) -> float:
    """
    Reward based on structured consensus and conflict vectors.
    """
    if not feedback_vector:
        return 0.0
    consensus = feedback_vector.get("consensus_score", 0.0)
    conflict = feedback_vector.get("conflict_level", 0.0)
    # Formula: +0.3 * consensus - 0.15 * conflict
    return (0.3 * consensus) - (0.15 * conflict)


def milestone_reward(
    phase_advanced: bool,
    phase_reward_weight: float = 1.0,
) -> float:
    """
    One-time bonus when agent completes a mission phase.

    Returns:
        +0.5 × weight if phase advanced, else 0.0
    """
    if phase_advanced:
        return 0.5 * phase_reward_weight
    return 0.0


def phase_progress_reward(
    phase_progress: float,
    phase_reward_weight: float = 1.0,
) -> float:
    """
    Continuous signal proportional to progress within the current phase.

    Args:
        phase_progress: 0.0 to 1.0

    Returns:
        Reward in range [0.0, +0.2] scaled by weight
    """
    return min(phase_progress, 1.0) * 0.2 * phase_reward_weight


def tool_usage_reward(
    tools_used: int = 0,
    max_bonus: float = 0.25,
) -> float:
    """
    Rewards +0.05 per tool used, capped at max_bonus to prevent spam hacking.
    """
    if tools_used > 0:
        return min(tools_used * 0.05, max_bonus)
    return 0.0

def communication_reward(
    action: FeatureFlagAction,
    error_rate: float,
    communications_sent: int = 0,
    max_bonus: float = 0.3,
) -> float:
    """
    Independent reward for communicating via Slack.
    Bonus doubles during critical scenarios (high error rate).
    """
    is_comm = False
    if action.action_type == "TOOL_CALL" and action.tool_call and action.tool_call.get("tool_name", "") == "slack":
        is_comm = True
    
    if not is_comm:
        return 0.0

    # Approximate cap check based on historical communications sent
    current_reward_basis = communications_sent * 0.1
    if current_reward_basis >= max_bonus:
        return 0.0
        
    if error_rate > 0.05:
        return min(0.15, max_bonus - current_reward_basis)
    return min(0.10, max_bonus - current_reward_basis)

def exploration_reward(
    action: FeatureFlagAction,
    recent_actions: list = None,
) -> float:
    """
    Encourages action diversity by supplying +0.05 when a new action type 
    is attempted outside the recent 10-step window constraint.
    """
    if not recent_actions:
        return 0.05
    recent_10 = recent_actions[-10:]
    recent_types = [a.action_type for a in recent_10 if hasattr(a, 'action_type')]
    if action.action_type not in recent_types:
        return 0.05
    return 0.0


def tool_failure_penalty(
    observation: FeatureFlagObservation,
    action: FeatureFlagAction,
) -> float:
    """
    Penalizes if the current action is a tool call that failed or was attempted when tools are disabled.
    """
    if action.action_type != "TOOL_CALL":
        return 0.0
    
    tr = observation.last_tool_result
    # If tr is None or success is explicitly False, it's a failure.
    if tr is None:
        return -2.5
    
    if not tr.get("success", False):
        return -2.5
        
    return 0.0


# ---------------------------------------------------------------------------
# Composite reward
# ---------------------------------------------------------------------------

def _get_extended_clip_config():
    """Read clipping config (mirrors base reward clipping)."""
    clip_env = os.environ.get("FEATURE_FLAG_REWARD_CLIP", "1")
    clip_enabled = clip_env != "0"
    clip_min = float(os.environ.get("FEATURE_FLAG_REWARD_CLIP_MIN", "-1.5"))
    clip_max = float(os.environ.get("FEATURE_FLAG_REWARD_CLIP_MAX", "1.5"))
    return clip_enabled, clip_min, clip_max


def calculate_extended_reward(
    old_observation: FeatureFlagObservation,
    new_observation: FeatureFlagObservation,
    action: FeatureFlagAction,
    *,
    stakeholder_feedback_dict: Optional[Dict[str, float]] = None,
    phase_advanced: bool = False,
    phase_progress_value: float = 0.0,
    phase_reward_weight: float = 1.0,
    tools_used: int = 0,
    communications_sent: int = 0,
    action_history: list = None,
    base_reward_fn=None,
    tool_reward_bonus: float = 0.0,
) -> float:
    """
    Calculate total reward = base_reward + extended components.

    If no extended signals are provided, this degrades to the base reward.
    """
    # 1. Base reward (reuses existing function)
    reward_fn = base_reward_fn or calculate_reward
    base = reward_fn(old_observation, new_observation, action)

    # 2. Stakeholder component
    stk = stakeholder_satisfaction_reward(stakeholder_feedback_dict or {})

    # 3. Milestone component
    mst = milestone_reward(phase_advanced, phase_reward_weight)

    # 4. Phase progress component
    ppg = phase_progress_reward(phase_progress_value, phase_reward_weight)

    # 5. Tool usage component
    tul = tool_usage_reward(tools_used)

    # 6. Communication (Slack) component
    com = communication_reward(action, old_observation.error_rate, communications_sent)

    # 7. Exploration component
    exp = exploration_reward(action, action_history)

    # 8. Tool Failure Penalty
    tfp = tool_failure_penalty(new_observation, action)

    total = base + stk + mst + ppg + tul + com + exp + tfp + tool_reward_bonus

    # Clip
    clip_enabled, clip_min, clip_max = _get_extended_clip_config()
    if clip_enabled:
        total = max(clip_min, min(clip_max, total))

    return total
