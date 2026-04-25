"""
tests/ultimate_stress_test.py

Executes a comprehensive, multi-episode stress test of the entire pipeline.
Enables all plugins: Stakeholders, Missions, Tools, Chaos, HITL, Patterns, Anomalies.
"""

import sys
import os
import random
import logging

# Ensure we can import the environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from feature_flag_env.server.feature_flag_environment import make_environment
from feature_flag_env.models import FeatureFlagAction
from feature_flag_env.historical_patterns import CustomerProfile

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("StressTest")

def run_episode(env, episode_num):
    logger.info(f"--- Starting Episode {episode_num} ---")
    obs = env.reset()
    done = False
    step = 0
    total_reward = 0.0

    while not done and step < 100:
        step += 1
        
        # Decide action type
        if random.random() < 0.2:
            # Randomly call a tool
            tool = random.choice(["github", "datadog", "slack"])
            action_type = "TOOL_CALL"
            target_pct = obs.current_rollout_percentage
            tool_call = {
                "tool_name": tool,
                "action_name": "get_status" if tool != "slack" else "send_message",
                "params": {"message": "Stress test status"} if tool == "slack" else {}
            }
        else:
            # Deployment actions
            action_type = random.choice(["INCREASE_ROLLOUT", "MAINTAIN", "DECREASE_ROLLOUT"])
            if action_type == "INCREASE_ROLLOUT":
                target_pct = min(100.0, obs.current_rollout_percentage + 10.0)
            elif action_type == "DECREASE_ROLLOUT":
                target_pct = max(0.0, obs.current_rollout_percentage - 10.0)
            else:
                target_pct = obs.current_rollout_percentage
            tool_call = None

        action = FeatureFlagAction(
            action_type=action_type,
            target_percentage=target_pct,
            reason=f"Stress test step {step}",
            tool_call=tool_call
        )

        try:
            response = env.step(action)
            obs = response.observation
            done = response.done
            total_reward += response.reward
            
            if step % 10 == 0:
                logger.info(f"Step {step}: Rollout={obs.current_rollout_percentage:.1f}%, Reward={total_reward:.2f}")
                if obs.chaos_incident:
                    logger.warning(f"CHAOS DETECTED: {obs.chaos_incident['type']}")
                if obs.extra_context.get("anomaly") and obs.extra_context["anomaly"].get("anomaly_score", 0) > 0.5:
                    logger.warning(f"ANOMALY DETECTED: {obs.extra_context['anomaly']['explanation']}")
        
        except Exception as e:
            logger.error(f"CRASH AT STEP {step}: {e}")
            raise e

    logger.info(f"Episode {episode_num} Complete. Total Steps: {step}, Total Reward: {total_reward:.2f}, Final Rollout: {obs.current_rollout_percentage:.1f}%")
    return total_reward

def main():
    # Setup environment with all plugins enabled
    profile = CustomerProfile(
        customer_id="enterprise_corp",
        historical_patterns=[],
        risk_weights={"latency": 1.2, "error": 1.5}
    )

    env = make_environment(
        mission_config="enterprise_payment_gateway", # Use a mission
        stakeholders_enabled=True,
        tools_enabled=True,
        chaos_enabled=True,
        hitl_enabled=True
    )
    env.set_customer_profile(profile)

    num_episodes = 5
    rewards = []
    
    logger.info("Starting Ultimate Stress Test...")
    for i in range(num_episodes):
        reward = run_episode(env, i + 1)
        rewards.append(reward)

    avg_reward = sum(rewards) / len(rewards)
    logger.info(f"Stress Test Finished. Average Reward: {avg_reward:.2f}")
    print("\n--- STRESS TEST RESULT ---")
    print(f"Episodes: {num_episodes}")
    print(f"Average Reward: {avg_reward:.2f}")
    print("Status: SUCCESS (No Crashes)")

if __name__ == "__main__":
    main()
