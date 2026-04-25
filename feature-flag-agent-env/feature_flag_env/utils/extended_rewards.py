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
    sentiments: Dict[str, float],
) -> float:
    """
    Reward based on average stakeholder satisfaction.

    Args:
        sentiments: mapping of role → satisfaction score [0, 1]

    Returns:
        Reward in range [-0.3, +0.3]
    """
    if not sentiments:
        return 0.0
    avg = sum(sentiments.values()) / len(sentiments)
    # Map [0, 1] satisfaction to [-0.3, +0.3]
    return (avg - 0.5) * 0.6


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
    max_bonus: float = 0.1,
) -> float:
    """
    Placeholder for future tool-usage incentives.
    Currently returns a small bonus if tools are connected/used.
    """
    if tools_used > 0:
        return min(tools_used * 0.03, max_bonus)
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
    stakeholder_sentiments: Optional[Dict[str, float]] = None,
    phase_advanced: bool = False,
    phase_progress_value: float = 0.0,
    phase_reward_weight: float = 1.0,
    tools_used: int = 0,
    base_reward_fn=None,
) -> float:
    """
    Calculate total reward = base_reward + extended components.

    If no extended signals are provided, this degrades to the base reward.
    """
    # 1. Base reward (reuses existing function)
    reward_fn = base_reward_fn or calculate_reward
    base = reward_fn(old_observation, new_observation, action)

    # 2. Stakeholder component
    stk = stakeholder_satisfaction_reward(stakeholder_sentiments or {})

    # 3. Milestone component
    mst = milestone_reward(phase_advanced, phase_reward_weight)

    # 4. Phase progress component
    ppg = phase_progress_reward(phase_progress_value, phase_reward_weight)

    # 5. Tool usage component
    tul = tool_usage_reward(tools_used)

    total = base + stk + mst + ppg + tul

    # Clip
    clip_enabled, clip_min, clip_max = _get_extended_clip_config()
    if clip_enabled:
        total = max(clip_min, min(clip_max, total))

    return total
