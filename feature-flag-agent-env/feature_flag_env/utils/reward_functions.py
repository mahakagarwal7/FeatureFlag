"""
feature_flag_env/utils/reward_functions.py

Reward functions for the Feature Flag Environment.

This module contains the "learning signals" that tell the agent
whether its actions were good or bad.

Reward Design Principles:
1. Dense rewards: Feedback at every step (not just end of episode)
2. Shaped rewards: Guide behavior toward desired outcomes
3. Balanced: Don't over-penalize or over-reward any single metric
4. Task-aware: Different tasks may need different reward weighting
"""

from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation
from typing import Tuple


def calculate_reward(
    old_observation: FeatureFlagObservation,
    new_observation: FeatureFlagObservation,
    action: FeatureFlagAction,
) -> float:
    """
    Calculate reward for an agent's action.
    
    This is the MAIN reward function used during training.
    It combines multiple signals to guide the agent toward safe, effective rollouts.
    
    Args:
        old_observation: State before the action
        new_observation: State after the action
        action: The action the agent took
    
    Returns:
        float: Reward value (can be positive or negative)
    
    Reward Breakdown:
        - Progress reward: For increasing rollout safely
        - Error penalty: For high error rates (critical!)
        - Revenue bonus: For generating revenue
        - Adoption bonus: For increasing user adoption
        - Latency penalty: For high latency
        - Step penalty: Small penalty to encourage efficiency
        - Health bonus: For maintaining system health
    """
    reward = 0.0
    
    # =========================================================================
    # 1. PROGRESS REWARD (Encourage rollout advancement)
    # =========================================================================
    rollout_delta = new_observation.current_rollout_percentage - old_observation.current_rollout_percentage
    
    if rollout_delta > 0:
        # Reward for increasing rollout (but only if errors are low)
        if new_observation.error_rate < 0.05:
            reward += 0.5 * (rollout_delta / 100.0)  # Max +0.5 for 100% increase
        else:
            # Don't reward rollout if errors are high (discourages reckless scaling)
            reward += 0.1 * (rollout_delta / 100.0)
    elif rollout_delta < 0:
        # Small penalty for decreasing rollout (sometimes necessary, but not ideal)
        reward -= 0.2 * (abs(rollout_delta) / 100.0)
    
    # =========================================================================
    # 2. ERROR RATE PENALTY (Most critical - prevents outages!)
    # =========================================================================
    if new_observation.error_rate > 0.25:
        # Catastrophic failure - huge penalty
        reward -= 3.0
    elif new_observation.error_rate > 0.10:
        # High errors - significant penalty
        reward -= 1.5
    elif new_observation.error_rate > 0.05:
        # Moderate errors - medium penalty
        reward -= 0.5
    elif new_observation.error_rate < 0.02:
        # Low errors - small bonus
        reward += 0.3
    
    # =========================================================================
    # 3. REVENUE BONUS (Business incentive)
    # =========================================================================
    # Normalize revenue to reasonable scale (assume max ~$1000 per episode)
    revenue_bonus = min(new_observation.revenue_impact / 1000.0, 0.5)
    reward += revenue_bonus
    
    # =========================================================================
    # 4. ADOPTION BONUS (Encourage user engagement)
    # =========================================================================
    if new_observation.user_adoption_rate > old_observation.user_adoption_rate:
        reward += 0.2
    elif new_observation.user_adoption_rate < old_observation.user_adoption_rate:
        reward -= 0.1
    
    # =========================================================================
    # 5. LATENCY PENALTY (Performance matters)
    # =========================================================================
    if new_observation.latency_p99_ms > 300:
        # Very high latency - significant penalty
        reward -= 0.5
    elif new_observation.latency_p99_ms > 200:
        # Moderate latency - small penalty
        reward -= 0.2
    elif new_observation.latency_p99_ms < 100:
        # Excellent latency - small bonus
        reward += 0.1
    
    # =========================================================================
    # 6. STEP PENALTY (Encourage efficiency)
    # =========================================================================
    # Small penalty per step to discourage unnecessary actions
    reward -= 0.01
    
    # =========================================================================
    # 7. SYSTEM HEALTH BONUS (Composite metric)
    # =========================================================================
    reward += 0.2 * new_observation.system_health_score
    
    # =========================================================================
    # 8. ACTION-TYPE BONUSES (Encourage good decision patterns)
    # =========================================================================
    # Bonus for maintaining when errors are moderate (shows caution)
    if action.action_type == "MAINTAIN" and 0.05 <= new_observation.error_rate <= 0.10:
        reward += 0.1
    
    # Bonus for rolling back when errors are very high (shows good judgment)
    if action.action_type == "ROLLBACK" and old_observation.error_rate > 0.15:
        reward += 0.3
    
    # Penalty for rolling back when errors are low (overly cautious)
    if action.action_type == "ROLLBACK" and old_observation.error_rate < 0.03:
        reward -= 0.2
    
    # =========================================================================
    # FINAL REWARD
    # =========================================================================
    return float(reward)


# =============================================================================
# ALTERNATIVE REWARD FUNCTIONS (For different training strategies)
# =============================================================================

def calculate_reward_conservative(
    old_observation: FeatureFlagObservation,
    new_observation: FeatureFlagObservation,
    action: FeatureFlagAction,
) -> float:
    """
    Conservative reward function - prioritizes safety over speed.
    
    Use this for training agents that need to be extra cautious
    (e.g., enterprise features, critical infrastructure).
    """
    reward = 0.0
    
    # Heavy penalty for errors
    reward -= new_observation.error_rate * 10.0
    
    # Small reward for rollout progress
    rollout_delta = new_observation.current_rollout_percentage - old_observation.current_rollout_percentage
    reward += 0.1 * (rollout_delta / 100.0)
    
    # Health bonus
    reward += 0.3 * new_observation.system_health_score
    
    # Step penalty (encourage fewer actions)
    reward -= 0.02
    
    return float(reward)


def calculate_reward_aggressive(
    old_observation: FeatureFlagObservation,
    new_observation: FeatureFlagObservation,
    action: FeatureFlagAction,
) -> float:
    """
    Aggressive reward function - prioritizes speed over safety.
    
    Use this for training agents that need to scale quickly
    (e.g., viral features, low-risk experiments).
    """
    reward = 0.0
    
    # Big reward for rollout progress
    rollout_delta = new_observation.current_rollout_percentage - old_observation.current_rollout_percentage
    reward += 1.0 * (rollout_delta / 100.0)
    
    # Moderate penalty for errors
    reward -= new_observation.error_rate * 5.0
    
    # Revenue bonus (emphasize business value)
    reward += 0.5 * (new_observation.revenue_impact / 1000.0)
    
    # Adoption bonus
    reward += 0.3 * new_observation.user_adoption_rate
    
    return float(reward)


# =============================================================================
# TASK-SPECIFIC REWARD FUNCTIONS
# =============================================================================

def calculate_reward_task1(
    old_observation: FeatureFlagObservation,
    new_observation: FeatureFlagObservation,
    action: FeatureFlagAction,
) -> float:
    """
    Reward function for Task 1: Safe Small Rollout (0% → 25%)
    
    Emphasizes:
    - Reaching 25% rollout
    - Keeping errors < 5%
    - No rollbacks
    """
    reward = 0.0
    
    # Progress toward 25% goal
    target = 25.0
    progress = min(new_observation.current_rollout_percentage / target, 1.0)
    reward += 2.0 * progress
    
    # Error penalty (stricter for this task)
    if new_observation.error_rate > 0.05:
        reward -= 2.0
    
    # Rollback penalty
    if action.action_type == "ROLLBACK":
        reward -= 1.0
    
    return float(reward)


def calculate_reward_task2(
    old_observation: FeatureFlagObservation,
    new_observation: FeatureFlagObservation,
    action: FeatureFlagAction,
) -> float:
    """
    Reward function for Task 2: Risk-Aware Scaling (Handle Incidents)
    
    Emphasizes:
    - Reaching 75% rollout
    - Responding to incidents (decrease when errors spike)
    - Recovery after incidents
    """
    reward = 0.0
    
    # Progress toward 75% goal
    target = 75.0
    progress = min(new_observation.current_rollout_percentage / target, 1.0)
    reward += 1.5 * progress
    
    # Incident response bonus (decrease rollout when errors high)
    if old_observation.error_rate > 0.10 and action.target_percentage < old_observation.current_rollout_percentage:
        reward += 0.5  # Good response to incident!
    
    # Error penalty
    reward -= new_observation.error_rate * 5.0
    
    return float(reward)


def calculate_reward_task3(
    old_observation: FeatureFlagObservation,
    new_observation: FeatureFlagObservation,
    action: FeatureFlagAction,
) -> float:
    """
    Reward function for Task 3: Multi-Objective Optimization
    
    Emphasizes:
    - Maximizing cumulative revenue
    - Maintaining system health > 0.7
    - Achieving > 80% adoption
    - Zero catastrophic failures
    """
    reward = 0.0
    
    # Revenue focus
    reward += 0.5 * (new_observation.revenue_impact / 1000.0)
    
    # Adoption focus
    reward += 0.3 * new_observation.user_adoption_rate
    
    # Health maintenance
    if new_observation.system_health_score < 0.7:
        reward -= 0.5
    
    # Catastrophic failure (very heavy penalty)
    if new_observation.error_rate > 0.20:
        reward -= 3.0
    
    return float(reward)