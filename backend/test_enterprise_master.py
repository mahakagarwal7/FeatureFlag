import sys
import os
import torch
# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.enterprise_agent_v2 import EnterpriseAgentV2
from feature_flag_env.server.feature_flag_environment import make_environment

def run_master_test():
    print("="*60)
    print("ENTERPRISE MASTER V2: TOTAL PIPELINE VALIDATION")
    print("="*60)
    
    model_path = "models/enterprise_master_v2.best.pth"
    if not os.path.exists(model_path):
        print(f"ERROR: Model not found at {model_path}")
        return

    # 1. Initialize the 22-dimensional Agent
    print(f"[*] Initializing EnterpriseAgentV2 (22 Dimensions)...")
    agent = EnterpriseAgentV2(
        task="task3",
        model_path=model_path,
        training=False,
        epsilon=0.0 # Pure exploitation of the trained brain
    )
    
    print(f"[*] Loading Master Weights from {model_path}...")
    # The agent auto-loads in __init__, but let's confirm dimension
    print(f"[*] Agent State Dimension: {agent.state_dim}")
    
    # 2. Setup a High-Risk Enterprise Scenario
    print("[*] Creating 'High Risk' Enterprise Scenario...")
    env = make_environment({
        "scenario_name": "high_risk",
        "tenant_id": "meta_enterprise_01",
        "service_name": "payment-gateway"
    })
    
    obs = env.reset()
    done = False
    total_reward = 0
    step = 0
    
    print("\n--- Starting Live Inference ---")
    while not done and step < 20:
        step += 1
        # DECISION PHASE
        action = agent.decide(obs, [])
        
        # EXECUTION PHASE
        response = env.step(action)
        obs = response.observation
        reward = response.reward
        done = response.done
        
        total_reward += reward
        
        print(f"Step {step:02d} | Action: {action.action_type:15s} | Rollout: {obs.current_rollout_percentage:5.1f}% | Health: {obs.system_health_score:.2f} | Reward: {reward:+.3f}")
        
        if done:
            print("\nRollout Lifecycle Completed.")
            break
            
    print("="*60)
    print(f"FINAL SCORE: {total_reward:+.3f}")
    if total_reward > 10:
        print("RESULT: EXCELLENT. Agent successfully navigated high-risk scenarios.")
    elif total_reward > 0:
        print("RESULT: STABLE. Agent completed rollout safely.")
    else:
        print("RESULT: SUBOPTIMAL. Further training or tuning recommended.")
    print("="*60)

if __name__ == "__main__":
    run_master_test()
