
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation
from feature_flag_env.utils.reward_functions import calculate_reward, calculate_reward_task1


def test_reward_function():
    """Test that reward calculation works"""
    print("🧪 Testing Reward Function...")
    
    
    old_obs = FeatureFlagObservation(
        current_rollout_percentage=0.0,
        error_rate=0.01,
        latency_p99_ms=100.0,
        user_adoption_rate=0.0,
        revenue_impact=0.0,
        system_health_score=0.99,
        active_users=0,
        feature_name="test_feature",
        time_step=0,
    )
    
    
    new_obs = FeatureFlagObservation(
        current_rollout_percentage=10.0,
        error_rate=0.02,
        latency_p99_ms=105.0,
        user_adoption_rate=0.05,
        revenue_impact=50.0,
        system_health_score=0.95,
        active_users=500,
        feature_name="test_feature",
        time_step=1,
    )
    
   
    action = FeatureFlagAction(
        action_type="INCREASE_ROLLOUT",
        target_percentage=10.0,
        reason="Starting rollout"
    )
    
 
    reward = calculate_reward(old_obs, new_obs, action)
    
    print(f"   ✅ Reward calculated: {reward:+.2f}")
    
   
    assert reward > 0, "Reward should be positive for safe rollout increase"
    
    print("   ✅ Reward function working correctly!")
    return True


def test_reward_high_errors():
    """Test that high errors get negative reward"""
    print("\n🧪 Testing Reward with High Errors...")
    
    old_obs = FeatureFlagObservation(
        current_rollout_percentage=10.0,
        error_rate=0.02,
        latency_p99_ms=100.0,
        user_adoption_rate=0.05,
        revenue_impact=50.0,
        system_health_score=0.95,
        active_users=500,
        feature_name="test_feature",
        time_step=1,
    )
    

    new_obs = FeatureFlagObservation(
        current_rollout_percentage=50.0,
        error_rate=0.20,  
        latency_p99_ms=250.0,
        user_adoption_rate=0.10,
        revenue_impact=100.0,
        system_health_score=0.50,
        active_users=1000,
        feature_name="test_feature",
        time_step=2,
    )
    
    action = FeatureFlagAction(
        action_type="INCREASE_ROLLOUT",
        target_percentage=50.0,
        reason="Aggressive scaling"
    )
    
    reward = calculate_reward(old_obs, new_obs, action)
    
    print(f"   ✅ Reward calculated: {reward:+.2f}")
    
    
    assert reward < 0, "Reward should be negative for high error rollout"
    
    print("   ✅ High error penalty working correctly!")
    return True


def test_task1_target_behavior():
    """Task1 should prefer 25% target band and penalize large overshoot."""
    print("\n🧪 Testing Task1 Target-Centered Reward...")

    old_obs = FeatureFlagObservation(
        current_rollout_percentage=0.0,
        error_rate=0.01,
        latency_p99_ms=100.0,
        user_adoption_rate=0.0,
        revenue_impact=0.0,
        system_health_score=0.95,
        active_users=0,
        feature_name="test_feature",
        time_step=0,
    )

    obs_20 = FeatureFlagObservation(
        current_rollout_percentage=20.0,
        error_rate=0.01,
        latency_p99_ms=100.0,
        user_adoption_rate=0.0,
        revenue_impact=0.0,
        system_health_score=0.95,
        active_users=0,
        feature_name="test_feature",
        time_step=1,
    )
    obs_25 = FeatureFlagObservation(
        current_rollout_percentage=25.0,
        error_rate=0.01,
        latency_p99_ms=100.0,
        user_adoption_rate=0.0,
        revenue_impact=0.0,
        system_health_score=0.95,
        active_users=0,
        feature_name="test_feature",
        time_step=1,
    )
    obs_100 = FeatureFlagObservation(
        current_rollout_percentage=100.0,
        error_rate=0.01,
        latency_p99_ms=100.0,
        user_adoption_rate=0.0,
        revenue_impact=0.0,
        system_health_score=0.95,
        active_users=0,
        feature_name="test_feature",
        time_step=1,
    )

    a_inc = FeatureFlagAction(
        action_type="INCREASE_ROLLOUT",
        target_percentage=25.0,
        reason="Move toward target",
    )
    a_full = FeatureFlagAction(
        action_type="FULL_ROLLOUT",
        target_percentage=100.0,
        reason="Overshoot",
    )

    prev_clip = os.environ.get("FEATURE_FLAG_REWARD_CLIP")
    os.environ["FEATURE_FLAG_REWARD_CLIP"] = "0"
    try:
        r20 = calculate_reward_task1(old_obs, obs_20, a_inc)
        r25 = calculate_reward_task1(old_obs, obs_25, a_inc)
        r100 = calculate_reward_task1(old_obs, obs_100, a_full)
    finally:
        if prev_clip is None:
            os.environ.pop("FEATURE_FLAG_REWARD_CLIP", None)
        else:
            os.environ["FEATURE_FLAG_REWARD_CLIP"] = prev_clip

    print(f"   r20={r20:+.2f} r25={r25:+.2f} r100={r100:+.2f}")

    assert r25 > r20, "Task1 reward should prefer hitting target over stopping short"
    assert r100 < 0, "Task1 reward should penalize full rollout overshoot"

    print("   ✅ Task1 target-centered reward behavior is correct!")
    return True


def main():
    print("=" * 60)
    print("🚀 REWARD FUNCTION TESTS")
    print("=" * 60)
    
    results = []
    results.append(test_reward_function())
    results.append(test_reward_high_errors())
    results.append(test_task1_target_behavior())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ ALL REWARD TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED.")
    print("=" * 60)


if __name__ == "__main__":
    main()