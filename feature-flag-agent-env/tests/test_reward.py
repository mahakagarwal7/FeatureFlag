
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation
from feature_flag_env.utils.reward_functions import calculate_reward


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


def main():
    print("=" * 60)
    print("🚀 REWARD FUNCTION TESTS")
    print("=" * 60)
    
    results = []
    results.append(test_reward_function())
    results.append(test_reward_high_errors())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ ALL REWARD TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED.")
    print("=" * 60)


if __name__ == "__main__":
    main()