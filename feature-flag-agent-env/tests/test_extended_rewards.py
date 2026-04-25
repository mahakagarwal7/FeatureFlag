"""
tests/test_extended_rewards.py

Tests for the extended reward components.
Run with: python tests/test_extended_rewards.py
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation
from feature_flag_env.utils.extended_rewards import (
    stakeholder_satisfaction_reward,
    milestone_reward,
    phase_progress_reward,
    tool_usage_reward,
    calculate_extended_reward,
)
from feature_flag_env.utils.reward_functions import calculate_reward


def _make_obs(**overrides):
    defaults = dict(
        current_rollout_percentage=10.0,
        error_rate=0.02,
        latency_p99_ms=110.0,
        user_adoption_rate=0.05,
        revenue_impact=50.0,
        system_health_score=0.9,
        active_users=500,
        feature_name="test_feature",
        time_step=1,
    )
    defaults.update(overrides)
    return FeatureFlagObservation(**defaults)


def _make_action(**overrides):
    defaults = dict(
        action_type="INCREASE_ROLLOUT",
        target_percentage=10.0,
        reason="test",
    )
    defaults.update(overrides)
    return FeatureFlagAction(**defaults)


# --- Individual components -------------------------------------------------

def test_stakeholder_satisfaction():
    """Stakeholder reward should map satisfaction to [-0.3, +0.3]."""
    print("🧪 Stakeholder satisfaction reward...")

    # All happy (satisfaction = 1.0 → reward = +0.3)
    r = stakeholder_satisfaction_reward({"devops": 1.0, "product": 1.0, "customer_success": 1.0})
    assert abs(r - 0.3) < 0.01, f"Expected ~+0.3, got {r}"

    # All neutral (satisfaction = 0.5 → reward = 0.0)
    r = stakeholder_satisfaction_reward({"devops": 0.5, "product": 0.5, "customer_success": 0.5})
    assert abs(r) < 0.01, f"Expected ~0.0, got {r}"

    # All unhappy (satisfaction = 0.0 → reward = -0.3)
    r = stakeholder_satisfaction_reward({"devops": 0.0, "product": 0.0, "customer_success": 0.0})
    assert abs(r - (-0.3)) < 0.01, f"Expected ~-0.3, got {r}"

    # Empty → 0
    r = stakeholder_satisfaction_reward({})
    assert r == 0.0

    print("   ✅ Passed")
    return True


def test_milestone():
    """Milestone reward should give bonus on phase advance."""
    print("🧪 Milestone reward...")
    assert milestone_reward(True) == 0.5, "Should give +0.5 on advance"
    assert milestone_reward(False) == 0.0, "Should give 0 when no advance"
    assert milestone_reward(True, phase_reward_weight=2.0) == 1.0, "Should scale with weight"
    print("   ✅ Passed")
    return True


def test_phase_progress():
    """Phase progress should scale 0.0 to 0.2."""
    print("🧪 Phase progress reward...")
    assert phase_progress_reward(0.0) == 0.0
    r_half = phase_progress_reward(0.5)
    assert abs(r_half - 0.1) < 0.01, f"Expected ~0.1, got {r_half}"
    r_full = phase_progress_reward(1.0)
    assert abs(r_full - 0.2) < 0.01, f"Expected ~0.2, got {r_full}"
    print("   ✅ Passed")
    return True


def test_tool_usage():
    """Tool usage should give small bonus."""
    print("🧪 Tool usage reward...")
    assert tool_usage_reward(0) == 0.0
    r = tool_usage_reward(2)
    assert 0 < r <= 0.1, f"Expected small positive, got {r}"
    print("   ✅ Passed")
    return True


# --- Composite reward -------------------------------------------------------

def test_composite_backward_compatible():
    """Extended reward with no extras should match base reward."""
    print("🧪 Composite backward compatibility...")

    old_obs = _make_obs(current_rollout_percentage=0.0, time_step=0)
    new_obs = _make_obs(current_rollout_percentage=10.0, time_step=1)
    action = _make_action()

    # Disable clipping for comparison
    prev_clip = os.environ.get("FEATURE_FLAG_REWARD_CLIP")
    os.environ["FEATURE_FLAG_REWARD_CLIP"] = "0"
    try:
        base = calculate_reward(old_obs, new_obs, action)
        extended = calculate_extended_reward(old_obs, new_obs, action)
    finally:
        if prev_clip is None:
            os.environ.pop("FEATURE_FLAG_REWARD_CLIP", None)
        else:
            os.environ["FEATURE_FLAG_REWARD_CLIP"] = prev_clip

    assert abs(base - extended) < 0.01, \
        f"With no extras, extended ({extended:.3f}) should match base ({base:.3f})"
    print(f"   ✅ Base={base:.3f}, Extended={extended:.3f}")
    return True


def test_composite_with_all_components():
    """Extended reward with all components should be higher than base."""
    print("🧪 Composite with all components...")

    old_obs = _make_obs(current_rollout_percentage=0.0, time_step=0)
    new_obs = _make_obs(current_rollout_percentage=10.0, time_step=1)
    action = _make_action()

    prev_clip = os.environ.get("FEATURE_FLAG_REWARD_CLIP")
    os.environ["FEATURE_FLAG_REWARD_CLIP"] = "0"
    try:
        base = calculate_reward(old_obs, new_obs, action)
        extended = calculate_extended_reward(
            old_obs, new_obs, action,
            stakeholder_sentiments={"devops": 0.8, "product": 0.7, "customer_success": 0.9},
            phase_advanced=True,
            phase_progress_value=0.5,
            phase_reward_weight=1.0,
            tools_used=1,
        )
    finally:
        if prev_clip is None:
            os.environ.pop("FEATURE_FLAG_REWARD_CLIP", None)
        else:
            os.environ["FEATURE_FLAG_REWARD_CLIP"] = prev_clip

    assert extended > base, \
        f"Extended ({extended:.3f}) should be higher than base ({base:.3f}) with positive extras"
    print(f"   ✅ Base={base:.3f}, Extended={extended:.3f}")
    return True


# --- Main ------------------------------------------------------------------

def main():
    print("=" * 60)
    print("🚀 EXTENDED REWARD SYSTEM TESTS")
    print("=" * 60)

    results = [
        test_stakeholder_satisfaction(),
        test_milestone(),
        test_phase_progress(),
        test_tool_usage(),
        test_composite_backward_compatible(),
        test_composite_with_all_components(),
    ]

    print()
    print("=" * 60)
    if all(results):
        print("✅ ALL EXTENDED REWARD TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED.")
    print("=" * 60)


if __name__ == "__main__":
    main()
