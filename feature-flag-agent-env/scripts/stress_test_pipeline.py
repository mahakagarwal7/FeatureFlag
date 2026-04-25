"""
scripts/stress_test_pipeline.py

A full end-to-end simulation script to verify the robustness of the 
FeatureFlagEnvironment with all extended features enabled.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from feature_flag_env.server.feature_flag_environment import FeatureFlagEnvironment
from feature_flag_env.models import FeatureFlagAction
import time

def run_stress_test():
    print("🚀 Starting End-to-End Pipeline Stress Test...")
    
    # Initialize environment with full suite
    env = FeatureFlagEnvironment(
        mission_config="enterprise_payment_gateway",
        stakeholders_enabled=True,
        tools_enabled=True
    )
    obs = env.reset() # Returns FeatureFlagObservation
    
    print(f"✅ Initialized: {obs.mission_name} | Phase: {obs.current_phase}")
    
    # Step 1: Tool Call (Testing Feature 3 & 5)
    print("\n--- Step 1: Slack Tool Call ---")
    action = FeatureFlagAction(
        action_type="TOOL_CALL",
        target_percentage=0.0,
        tool_call={"tool_name": "slack", "action_name": "send", "params": {"msg": "Starting stress test"}}
    )
    response = env.step(action)
    obs = response.observation
    reward = response.reward
    done = response.done
    print(f"Result: Reward={reward:.2f}, ToolResult={obs.last_tool_result.get('success') if obs.last_tool_result else 'N/A'}")
    
    # Step 2: Attempt Invalid action (Testing Phase Constraints)
    print("\n--- Step 2: Invalid Action (Regional in Analysis) ---")
    # canary phase in enterprise_payment_gateway allows ["INCREASE_ROLLOUT", "MAINTAIN", "ROLLBACK", "TOOL_CALL"]
    # and has target_rollout_max=5.0. 
    # Let's try 50%
    action = FeatureFlagAction(action_type="INCREASE_ROLLOUT", target_percentage=50.0)
    response = env.step(action)
    obs = response.observation
    reward = response.reward
    print(f"Result: Rollout={obs.current_rollout_percentage}%, Reward={reward:.2f} (Should be clamped to 5%)")
    
    # Step 3: Advance Phase (canary -> limited_beta)
    print("\n--- Step 3: Advancing to limited_beta ---")
    # To advance canary, we need rollout >= 5.0
    for i in range(5):
        action = FeatureFlagAction(action_type="INCREASE_ROLLOUT", target_percentage=5.0)
        response = env.step(action)
        obs = response.observation
        reward = response.reward
        done = response.done
        print(f"Step {i}: Phase={obs.current_phase}, Rollout={obs.current_rollout_percentage}%, Reward={reward:.2f}")
        if (obs.current_phase or "") == "limited_beta":
            break
            
    # Step 4: Full Walkthrough to completion
    print("\n--- Step 4: Rapid Rollout to Completion ---")
    steps = 0
    while not done and steps < 40:
        steps += 1
        # Try to increase rollout but respect potential blocks (limited_beta requires approval)
        # Approval is provided automatically by stakeholders in mock if error is low.
        pct = min(100.0, obs.current_rollout_percentage + 10.0)
        action = FeatureFlagAction(action_type="INCREASE_ROLLOUT", target_percentage=pct)
        response = env.step(action)
        obs = response.observation
        reward = response.reward
        done = response.done
        
        print(f"Step {steps}: Phase={obs.current_phase}, Rollout={obs.current_rollout_percentage}%, Reward={reward:.2f}, Done={done}")
        
    print("\n--- Final Stats ---")
    print(f"Total Steps: {env._state.step_count}")
    print(f"Total Reward: {env._state.total_reward:.2f}")
    print(f"Final Rollout: {obs.current_rollout_percentage}%")
    print(f"Mission Complete: {done}")
    
    if done and obs.current_rollout_percentage >= 100.0:
        print("\n✅ SUCCESS: End-to-end pipeline is solid.")
    else:
        print("\n⚠️ WARNING: Pipeline ended prematurely or didn't reach 100%.")

if __name__ == "__main__":
    run_stress_test()
