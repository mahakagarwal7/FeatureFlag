"""
tests/test_stakeholders.py

Tests for the multi-stakeholder feedback system.
Run with: python tests/test_stakeholders.py
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from feature_flag_env.models import FeatureFlagObservation
from feature_flag_env.stakeholders import (
    DevOpsStakeholder,
    ProductStakeholder,
    CustomerSuccessStakeholder,
    StakeholderPanel,
    StakeholderRole,
)


def _make_obs(**overrides):
    defaults = dict(
        current_rollout_percentage=10.0,
        error_rate=0.02,
        latency_p99_ms=120.0,
        user_adoption_rate=0.1,
        revenue_impact=100.0,
        system_health_score=0.9,
        active_users=1000,
        feature_name="test_feature",
        time_step=1,
    )
    defaults.update(overrides)
    return FeatureFlagObservation(**defaults)


# --- DevOps ----------------------------------------------------------------

def test_devops_happy():
    """DevOps should be happy when errors and latency are low."""
    print("🧪 DevOps happy path...")
    s = DevOpsStakeholder()
    fb = s.get_feedback(_make_obs(error_rate=0.01, latency_p99_ms=100.0, system_health_score=0.95))
    assert fb.sentiment > 0, f"Expected positive sentiment, got {fb.sentiment}"
    assert fb.approval is True, "DevOps should approve healthy metrics"
    assert len(fb.priority_concerns) == 0
    print("   ✅ Passed")
    return True


def test_devops_unhappy():
    """DevOps should flag high errors."""
    print("🧪 DevOps unhappy path...")
    s = DevOpsStakeholder()
    fb = s.get_feedback(_make_obs(error_rate=0.20, latency_p99_ms=450.0, system_health_score=0.3))
    assert fb.sentiment < 0, f"Expected negative sentiment, got {fb.sentiment}"
    assert fb.approval is False
    assert len(fb.priority_concerns) > 0
    print("   ✅ Passed")
    return True


# --- Product ---------------------------------------------------------------

def test_product_happy():
    """Product should be happy when rollout is growing and adoption is good."""
    print("🧪 Product happy path...")
    s = ProductStakeholder()
    # First call sets baseline
    s.get_feedback(_make_obs(current_rollout_percentage=0.0, user_adoption_rate=0.1))
    fb = s.get_feedback(_make_obs(current_rollout_percentage=20.0, user_adoption_rate=0.4))
    assert fb.sentiment > 0, f"Expected positive sentiment, got {fb.sentiment}"
    print("   ✅ Passed")
    return True


def test_product_stalled():
    """Product should be concerned when rollout is stalled."""
    print("🧪 Product stalled rollout...")
    s = ProductStakeholder()
    s.get_feedback(_make_obs(current_rollout_percentage=10.0, user_adoption_rate=0.05))
    fb = s.get_feedback(_make_obs(current_rollout_percentage=10.0, user_adoption_rate=0.05))
    assert any("velocity" in c or "low" in c for c in fb.priority_concerns), \
        f"Expected velocity/adoption concern, got {fb.priority_concerns}"
    print("   ✅ Passed")
    return True


# --- Customer Success ------------------------------------------------------

def test_customer_happy():
    """Customer success should be happy when users are satisfied."""
    print("🧪 Customer Success happy path...")
    s = CustomerSuccessStakeholder()
    fb = s.get_feedback(_make_obs(
        user_adoption_rate=0.7, system_health_score=0.9,
        error_rate=0.01, active_users=5000, revenue_impact=500.0,
    ))
    assert fb.sentiment > 0, f"Expected positive sentiment, got {fb.sentiment}"
    assert fb.approval is True
    print("   ✅ Passed")
    return True


def test_customer_complaint_risk():
    """High errors with many active users should trigger complaint risk."""
    print("🧪 Customer Success complaint risk...")
    s = CustomerSuccessStakeholder()
    fb = s.get_feedback(_make_obs(
        user_adoption_rate=0.1, system_health_score=0.5,
        error_rate=0.15, active_users=8000,
    ))
    assert any("complaint" in c for c in fb.priority_concerns), \
        f"Expected complaint concern, got {fb.priority_concerns}"
    print("   ✅ Passed")
    return True


# --- Panel -----------------------------------------------------------------

def test_panel():
    """StakeholderPanel should aggregate all three stakeholders."""
    print("🧪 Panel aggregation...")
    panel = StakeholderPanel()
    panel.reset()
    obs = _make_obs(error_rate=0.01, latency_p99_ms=100.0, system_health_score=0.95,
                    user_adoption_rate=0.5, active_users=5000, revenue_impact=500.0,
                    current_rollout_percentage=30.0)
    feedbacks = panel.get_all_feedback(obs)

    assert StakeholderRole.DEVOPS in feedbacks
    assert StakeholderRole.PRODUCT in feedbacks
    assert StakeholderRole.CUSTOMER_SUCCESS in feedbacks

    # All should be relatively happy with good metrics
    for role, fb in feedbacks.items():
        assert -1.0 <= fb.sentiment <= 1.0, f"{role} sentiment out of range: {fb.sentiment}"

    print("   ✅ Passed")
    return True


def test_satisfaction_ema():
    """Satisfaction EMA should smooth over time."""
    print("🧪 Satisfaction EMA tracking...")
    s = DevOpsStakeholder()
    # Feed several good observations
    for _ in range(5):
        s.get_feedback(_make_obs(error_rate=0.01, latency_p99_ms=100.0, system_health_score=0.95))
    high_sat = s.satisfaction

    # Feed bad observations
    for _ in range(5):
        s.get_feedback(_make_obs(error_rate=0.20, latency_p99_ms=500.0, system_health_score=0.3))
    low_sat = s.satisfaction

    assert high_sat > low_sat, f"Satisfaction should decrease: {high_sat} -> {low_sat}"
    print(f"   ✅ EMA: {high_sat:.3f} → {low_sat:.3f}")
    return True


# --- Main ------------------------------------------------------------------

def main():
    print("=" * 60)
    print("🚀 STAKEHOLDER FEEDBACK SYSTEM TESTS")
    print("=" * 60)

    results = [
        test_devops_happy(),
        test_devops_unhappy(),
        test_product_happy(),
        test_product_stalled(),
        test_customer_happy(),
        test_customer_complaint_risk(),
        test_panel(),
        test_satisfaction_ema(),
    ]

    print()
    print("=" * 60)
    if all(results):
        print("✅ ALL STAKEHOLDER TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED.")
    print("=" * 60)


if __name__ == "__main__":
    main()
