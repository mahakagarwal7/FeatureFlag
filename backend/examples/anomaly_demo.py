"""
examples/anomaly_demo.py

Tests the Anomaly Detection side-car in a real episode loop with Chaos Engine.
"""

from feature_flag_env.server.feature_flag_environment import FeatureFlagEnvironment
from feature_flag_env.models import FeatureFlagAction

def run_demo():
    print("Initializing environment with Chaos Engine...")
    env = FeatureFlagEnvironment(
        scenario_config={"scenario_name": "moderate_risk"},
        chaos_enabled=True
    )
    
    obs = env.reset()
    print(f"Initial State: Rollout={obs.current_rollout_percentage}%, Error={obs.error_rate:.4f}")

    # Baseline Phase (Step 0-10): Smooth rollout
    for i in range(1, 11):
        action = FeatureFlagAction(
            action_type="INCREASE_ROLLOUT",
            target_percentage=float(i * 5),
            reason="Baseline rollout"
        )
        res = env.step(action)
        obs = res.observation
        anom = obs.extra_context.get("anomaly", {})
        print(f"Step {i}: Rollout={obs.current_rollout_percentage}%, Score={anom.get('anomaly_score', 0)}")

    print("\n--- Triggering Anomalies (Step 11-15) ---")
    # Forcing a chaos incident if it hasn't happened
    if env._chaos_engine:
        env._chaos_engine.active_incident = {
            "type": "latency_spike",
            "intensity": 5.0, # 500% increase
            "duration": 3,
            "metric": "latency_p99_ms"
        }

    for i in range(11, 16):
        action = FeatureFlagAction(
            action_type="MAINTAIN",
            target_percentage=obs.current_rollout_percentage,
            reason="Monitoring anomaly"
        )
        res = env.step(action)
        obs = res.observation
        anom = obs.extra_context.get("anomaly", {})
        
        print(f"Step {i}: Rollout={obs.current_rollout_percentage}%")
        print(f"  Anomaly Score: {anom.get('anomaly_score')}")
        print(f"  Anomalies: {anom.get('anomalies')}")
        print(f"  Explanation: {anom.get('explanation')}")
        print(f"  Reward: {res.reward:.4f}") # Should see penalty if score > 0.6

    print("\nDemo completed.")

if __name__ == "__main__":
    run_demo()
