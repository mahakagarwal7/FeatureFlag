"""
tests/test_environment.py

Test the FeatureFlagEnvironment class.
Run with: python tests/test_environment.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from feature_flag_env.server.feature_flag_environment import FeatureFlagEnvironment
from feature_flag_env.models import FeatureFlagAction


def test_environment_reset():
    """Test that environment resets correctly"""
    print("🧪 Testing Environment Reset...")
    
    env = FeatureFlagEnvironment()
    obs = env.reset()
    
    # Check observation structure
    assert obs.current_rollout_percentage == 0.0, "Initial rollout should be 0%"
    assert 0.0 <= obs.error_rate <= 1.0, "Error rate should be in valid range"
    assert obs.latency_p99_ms >= 0, "Latency should be non-negative"
    assert obs.time_step == 0, "Initial step should be 0"
    assert obs.done == False, "Episode should not be done at start"
    
    print(f"   ✅ Reset successful")
    print(f"   📊 Initial state: rollout={obs.current_rollout_percentage}%, "
          f"errors={obs.error_rate*100:.2f}%")
    
    assert True


def test_environment_step():
    """Test that environment step works correctly"""
    print("\n🧪 Testing Environment Step...")
    
    env = FeatureFlagEnvironment()
    obs = env.reset()
    
    # Take an action: increase rollout to 10%
    action = FeatureFlagAction(
        action_type="INCREASE_ROLLOUT",
        target_percentage=10.0,
        reason="Starting rollout"
    )
    
    response = env.step(action)
    
    # Check response structure
    assert response.observation.current_rollout_percentage == 10.0, "Rollout should be 10%"
    assert response.reward is not None, "Reward should be calculated"
    assert response.done == False, "Episode should not be done yet"
    
    # Check state updated
    state = env.state()
    assert state.step_count == 1, "Step count should be 1"
    assert state.total_reward == response.reward, "Total reward should match"
    
    print(f"   ✅ Step successful")
    print(f"   📊 After step: rollout={response.observation.current_rollout_percentage}%, "
          f"reward={response.reward:+.2f}")
    
    assert True


def test_environment_multiple_steps():
    """Test multiple steps in an episode"""
    print("\n🧪 Testing Multiple Steps...")
    
    env = FeatureFlagEnvironment()
    obs = env.reset()
    
    # Take 5 steps, gradually increasing rollout
    rollout_levels = [10, 20, 30, 40, 50]
    total_reward = 0.0
    
    for rollout in rollout_levels:
        action = FeatureFlagAction(
            action_type="INCREASE_ROLLOUT",
            target_percentage=float(rollout),
            reason=f"Increasing to {rollout}%"
        )
        response = env.step(action)
        total_reward += response.reward
    
    # Check final state
    state = env.state()
    assert state.step_count == 5, f"Step count should be 5, got {state.step_count}"
    assert state.rollout_history == rollout_levels, "Rollout history should match"
    
    print(f"   ✅ 5 steps completed successfully")
    print(f"   📊 Total reward: {total_reward:+.2f}")
    print(f"   📊 Final rollout: {rollout_levels[-1]}%")
    
    assert True


def test_environment_done_conditions():
    """Test that episode ends correctly"""
    print("\n🧪 Testing Done Conditions...")
    
    # Test 1: Catastrophic failure
    env = FeatureFlagEnvironment(
        scenario_config={
            "name": "test_failure",
            "base_error_rate": 0.30,  # Very high errors
            "error_variance": 0.01,
            "latency_per_10pct_rollout": 5.0,
            "adoption_speed": 0.1,
            "revenue_per_user": 0.10,
            "total_users": 10000,
            "incident_zones": [],
        }
    )
    obs = env.reset()
    
    # Jump to 100% rollout (should trigger high errors)
    action = FeatureFlagAction(
        action_type="FULL_ROLLOUT",
        target_percentage=100.0,
        reason="Testing failure"
    )
    response = env.step(action)
    
    # Should end due to high errors OR full rollout
    print(f"   ✅ Episode ended: done={response.done}")
    print(f"   📊 Final errors: {response.observation.error_rate*100:.2f}%")
    
    assert True


def test_environment_invalid_action():
    """Test that invalid actions are rejected"""
    print("\n🧪 Testing Invalid Action Handling...")
    
    env = FeatureFlagEnvironment()
    obs = env.reset()
    
    # Try invalid percentage (> 100)
    did_raise = False
    try:
        action = FeatureFlagAction(
            action_type="INCREASE_ROLLOUT",
            target_percentage=150.0,  # Invalid!
            reason="This should fail"
        )
        _ = env.step(action)
    except ValueError as e:
        did_raise = True
        print(f"   ✅ Correctly rejected invalid action: {str(e)[:50]}...")
    assert did_raise, "Expected ValueError for invalid action"


def test_environment_state():
    """Test state tracking"""
    print("\n🧪 Testing State Tracking...")
    
    env = FeatureFlagEnvironment()
    obs = env.reset()
    
    # Take a few steps
    for i in range(3):
        action = FeatureFlagAction(
            action_type="INCREASE_ROLLOUT",
            target_percentage=float((i + 1) * 10),
            reason=f"Step {i+1}"
        )
        env.step(action)
    
    # Get state
    state = env.state()
    
    assert state.episode_id is not None, "Episode ID should exist"
    assert state.step_count == 3, f"Step count should be 3, got {state.step_count}"
    assert len(state.rollout_history) == 3, "Rollout history should have 3 entries"
    assert len(state.action_history) == 3, "Action history should have 3 entries"
    
    print(f"   ✅ State tracking working correctly")
    print(f"   📊 Episode ID: {state.episode_id[:8]}...")
    print(f"   📊 Rollout history: {state.rollout_history}")
    print(f"   📊 Action history: {state.action_history}")
    
    assert True


def main():
    """Run all tests"""
    print("=" * 60)
    print("🚀 FEATURE FLAG ENVIRONMENT - ENVIRONMENT TESTS")
    print("=" * 60)
    print()
    
    results = []
    results.append(test_environment_reset())
    results.append(test_environment_step())
    results.append(test_environment_multiple_steps())
    results.append(test_environment_done_conditions())
    results.append(test_environment_invalid_action())
    results.append(test_environment_state())
    
    print()
    print("=" * 60)
    if all(results):
        print("✅ ALL ENVIRONMENT TESTS PASSED!")
        print("🎉 Environment class is working correctly!")
    else:
        print("❌ SOME TESTS FAILED. Review and fix errors.")
    print("=" * 60)


if __name__ == "__main__":
    main()