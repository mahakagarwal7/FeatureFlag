"""
tests/test_models.py

We test early to catch errors before they become complex bugs.
Run this with: python tests/test_models.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from feature_flag_env.models import (
    FeatureFlagAction,
    FeatureFlagObservation,
    FeatureFlagState,
    StepResponse
)
from pydantic import ValidationError

def test_action_validation():
    """Test that invalid actions are rejected"""
    print("🧪 Testing Action Validation...")
    
   
    try:
        action = FeatureFlagAction(
            action_type="INCREASE_ROLLOUT",
            target_percentage=25.0,
            reason="System is stable"
        )
        print(f"✅ Valid action created: {action}")
    except Exception as e:
        print(f"❌ Failed to create valid action: {e}")
        return False

  
    try:
        bad_action = FeatureFlagAction(
            action_type="INCREASE_ROLLOUT",
            target_percentage=150.0, 
            reason="Too high"
        )
        print("❌ Validation failed: Accepted 150%")
        return False
    except ValidationError:
        print("✅ Correctly rejected percentage > 100")

    
    try:
        bad_action = FeatureFlagAction(
            action_type="INVALID_ACTION",  
            target_percentage=50.0,
            reason="Wrong type"
        )
        print("❌ Validation failed: Accepted invalid action type")
        return False
    except ValidationError:
        print("✅ Correctly rejected invalid action type")
    
    return True

def test_observation_creation():
    """Test creating an observation"""
    print("\n🧪 Testing Observation Creation...")
    
    try:
        obs = FeatureFlagObservation(
            current_rollout_percentage=10.0,
            error_rate=0.02,
            latency_p99_ms=120.5,
            user_adoption_rate=0.05,
            revenue_impact=50.0,
            system_health_score=0.95,
            active_users=500,
            feature_name="test_feature",
            time_step=1
        )
        print(f"✅ Observation created: {obs}")
        
        
        prompt = obs.to_prompt_string()
        print(f"✅ Prompt string generated (length: {len(prompt)})")
        return True
    except Exception as e:
        print(f"❌ Failed to create observation: {e}")
        return False

def test_state_tracking():
    """Test episode state tracking"""
    print("\n🧪 Testing State Tracking...")
    
    try:
        state = FeatureFlagState(scenario_name="test_scenario")
        print(f"✅ State created: ID={state.episode_id[:8]}...")
        
        
        action = FeatureFlagAction(
            action_type="INCREASE_ROLLOUT",
            target_percentage=10.0,
            reason="Start"
        )
        state.add_step(action, reward=0.5)
        
        print(f"✅ Step added: Count={state.step_count}, Reward={state.total_reward}")
        print(f"✅ History: {state.rollout_history}")
        return True
    except Exception as e:
        print(f"❌ Failed state tracking: {e}")
        return False

def main():
    print("=" * 50)
    print("🚀 FEATURE FLAG ENV - MODEL TESTS")
    print("=" * 50)
    
    results = []
    results.append(test_action_validation())
    results.append(test_observation_creation())
    results.append(test_state_tracking())
    
    print("\n" + "=" * 50)
    if all(results):
        print("✅ ALL TESTS PASSED!")
        print("🎉 Foundation is solid. Ready for Simulation Engine.")
    else:
        print("❌ SOME TESTS FAILED. Fix errors before proceeding.")
    print("=" * 50)

if __name__ == "__main__":
    main()