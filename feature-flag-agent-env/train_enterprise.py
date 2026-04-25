#!/usr/bin/env python3
import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from train_rl import train
from agents.enterprise_agent_v2 import EnterpriseAgentV2
from agents.rl_agent import _make_env
import argparse

def main():
    parser = argparse.ArgumentParser(description="Train Enterprise Agent V2 (22-dim)")
    parser.add_argument("--task", default="task3")
    parser.add_argument("--episodes", type=int, default=1000)
    parser.add_argument("--save-model", default="models/enterprise_master_v2.pth")
    parser.add_argument("--scenario-mix", action="store_true")
    args = parser.parse_args()

    # Override the training loop to use EnterpriseAgentV2
    print(f"🚀 Starting Enterprise Master Training (22 Dimensions)")
    
    # We call the main train function from train_rl but we will have to monkeypatch 
    # or just replicate a small part. To be safe, we'll just run it with a custom agent factory.
    
    import agents.rl_agent
    original_rl_agent = agents.rl_agent.RLAgent
    agents.rl_agent.RLAgent = EnterpriseAgentV2 # Redirect factory to new agent
    
    try:
        train(
            task=args.task,
            episodes=args.episodes,
            batch_size=64,
            buffer_size=20000,
            learning_rate=0.001,
            gamma=0.99,
            epsilon_decay=0.995,
            epsilon_min=0.01,
            target_update_freq=200,
            save_model=args.save_model,
            log_dir="logs/enterprise",
            eval_every=100,
            checkpoint_every=500,
            scenario_mix=args.scenario_mix,
            mix_scenarios=["stable", "moderate_risk", "high_risk"],
            validation_episodes=5,
            early_stop_patience=0,
            best_model_path=args.save_model.replace(".pth", ".best.pth"),
            resume=False
        )
    finally:
        agents.rl_agent.RLAgent = original_rl_agent # Restore legacy

if __name__ == "__main__":
    main()
