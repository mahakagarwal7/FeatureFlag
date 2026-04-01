#!/usr/bin/env python3
"""
Training script for DQN agent with experience replay buffer.

This script implements the complete training loop with:
- Experience replay buffer for stable learning
- Target network for Q-value calculation
- Epsilon-decay for exploration-exploitation trade-off
- Periodic model checkpointing
- Training metrics logging

Usage:
    python train_rl.py --episodes 1000 --task task1
    python train_rl.py --episodes 500 --task task3 --batch-size 64
"""

import argparse
import json
import os
import random
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.metrics import MetricsTracker
from agents.rl_agent import RLAgent, _make_env
from feature_flag_env.server.feature_flag_environment import make_environment


def format_timestamp() -> str:
    """Get formatted timestamp for logging."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_episode(agent: RLAgent, env) -> Tuple[float, int, float, Dict[str, float]]:
    """
    Run a single training episode.
    
    Args:
        agent: RLAgent instance
        env: Environment instance
        
    Returns:
        Tuple of (total_reward, steps, average_reward_per_step, last_train_metrics)
    """
    obs = env.reset()
    episode_reward = 0.0
    step_count = 0
    history = []
    
    last_train_metrics: Dict[str, float] = {"loss": 0.0, "trained": False, "epsilon": float(agent.epsilon)}

    while not obs.done and env.state().step_count < env.state().max_steps:
        # Agent decides action
        action = agent.decide(obs, history)
        
        # Environment executes action
        response = env.step(action)
        next_obs = response.observation
        reward = response.reward
        done = response.done
        
        # Store transition in replay buffer
        agent.store_transition(obs, action, reward, next_obs, done)
        
        # Train on a random mini-batch sampled from replay memory.
        last_train_metrics = agent.train_step()
        
        # Update tracking
        episode_reward += reward
        step_count += 1
        history.append({
            "obs": obs,
            "action": action,
            "reward": reward,
            "next_obs": next_obs,
            "done": done,
        })
        
        obs = next_obs
        if done:
            break
    
    # Episode complete
    agent.on_episode_end(obs)
    avg_reward_per_step = episode_reward / max(step_count, 1)
    
    return episode_reward, step_count, avg_reward_per_step, last_train_metrics


def run_eval_episode(agent: RLAgent, env) -> Tuple[float, int]:
    """Run one evaluation episode without storing transitions."""
    obs = env.reset()
    total_reward = 0.0
    step_count = 0
    history = []

    while not obs.done and env.state().step_count < env.state().max_steps:
        action = agent.decide(obs, history)
        response = env.step(action)
        obs = response.observation
        total_reward += response.reward
        step_count += 1
        history.append({"obs": obs, "action": action, "reward": response.reward})
        if response.done:
            break

    agent.on_episode_end(obs)
    return total_reward, step_count


def make_mixed_env(task: str, scenario_key: Optional[str] = None):
    """Create per-episode environment, optionally forcing a scenario key."""
    if scenario_key is None:
        return _make_env(task)
    return make_environment({"scenario_name": scenario_key})


def print_header(title: str, width: int = 70):
    """Print a formatted header."""
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def print_episode_summary(
    episode: int,
    total_episodes: int,
    reward: float,
    avg_reward_10: float,
    steps: int,
    epsilon: float,
    buffer_stats: Dict,
):
    """Print episode training summary."""
    print(f"📍 Episode {episode + 1:5d}/{total_episodes}")
    print(f"   Reward: {reward:+.3f} | Avg(10): {avg_reward_10:+.3f}")
    print(f"   Steps: {steps:2d} | Epsilon: {epsilon:.4f}")
    print(f"   Buffer: {buffer_stats['size']:5d}/{buffer_stats['capacity']:5d} | "
          f"Avg Reward: {buffer_stats['avg_reward']:+.3f}")


def print_variance_health(
    values: List[float],
    label: str,
    near_zero_threshold: float = 1e-6,
    deterministic_eval: bool = False,
):
    """Print variance diagnostics and context-aware messaging for near-zero spread."""
    if not values:
        print(f"   {label} Variance: N/A (no samples)")
        return

    std_val = float(np.std(values))
    min_val = float(np.min(values))
    max_val = float(np.max(values))
    print(f"   {label} Variance: std={std_val:.4f} | range=[{min_val:+.3f}, {max_val:+.3f}]")

    if abs(max_val - min_val) <= near_zero_threshold:
        if deterministic_eval:
            print(
                f"   ✅ {label} spread is near-zero; this is expected for a stable "
                "deterministic evaluation policy."
            )
        else:
            print(
                f"   ⚠️ {label} spread is near-zero. "
                "If this is active training, check exploration and environment randomness."
            )
    

def train(
    task: str,
    episodes: int,
    batch_size: int,
    buffer_size: int,
    learning_rate: float,
    gamma: float,
    epsilon_decay: float,
    epsilon_min: float,
    target_update_freq: int,
    save_model: str,
    log_dir: str,
    eval_every: int,
    checkpoint_every: int,
    scenario_mix: bool,
    mix_scenarios: List[str],
    validation_episodes: int,
    early_stop_patience: int,
    best_model_path: Optional[str],
    resume: bool,
    verbose: bool = False,
):
    """
    Train the DQN agent.
    
    Args:
        task: Task name (task1, task2, task3)
        episodes: Number of training episodes
        batch_size: Batch size for training
        buffer_size: Replay buffer capacity
        learning_rate: Learning rate for optimizer
        gamma: Discount factor
        epsilon_decay: Epsilon decay rate
        target_update_freq: Update target network every N steps
        save_model: Path to save final model
        log_dir: Directory to save logs
        eval_every: Evaluate every N episodes
        checkpoint_every: Save checkpoint every N episodes
        verbose: Print verbose output
    """
    
    print_header("DQN Training with Experience Replay")
    print(f"[{format_timestamp()}] Starting training...")
    print(f"  Task: {task}")
    print(f"  Episodes: {episodes}")
    print(f"  Batch Size: {batch_size}")
    print(f"  Buffer Size: {buffer_size}")
    print(f"  Learning Rate: {learning_rate}")
    print(f"  Gamma: {gamma}")
    print(f"  Epsilon Decay: {epsilon_decay}")
    print(f"  Epsilon Min: {epsilon_min}")
    print(f"  Scenario Mix: {scenario_mix}")
    if scenario_mix:
        print(f"  Mix Scenarios: {mix_scenarios}")
    
    # Create environment and agent
    env = _make_env(task)
    should_load_checkpoint = bool(resume and os.path.exists(save_model))
    if resume and not os.path.exists(save_model):
        print(f"  ⚠️ Resume requested but checkpoint not found: {save_model}")
        print("  Starting fresh training run.")
    if not resume and os.path.exists(save_model):
        print(f"  ℹ️ Existing model found at {save_model}")
        print("  Starting fresh training (checkpoint auto-load disabled). Use --resume to continue.")

    agent = RLAgent(
        task=task,
        training=True,
        model_path=save_model,
        auto_load_model=should_load_checkpoint,
        gamma=gamma,
        lr=learning_rate,
        epsilon_decay=epsilon_decay,
        epsilon_min=epsilon_min,
        buffer_capacity=buffer_size,
        batch_size=batch_size,
        target_update_freq=target_update_freq,
    )
    agent.external_transition_mode = True
    
    # Create metrics tracker
    metrics = MetricsTracker(f"RL-{task}")
    
    # Training variables
    episode_rewards: List[float] = []
    episode_steps: List[int] = []
    episode_data: List[Dict] = []
    best_eval_score = float("-inf")
    patience_counter = 0
    if best_model_path is None:
        best_model_path = save_model.replace(".pth", ".best.pth")
    
    # Create log directory
    os.makedirs(log_dir, exist_ok=True)
    
    # Start training loop
    print_header("Training Progress")
    
    for episode in range(episodes):
        if scenario_mix and task == "task2":
            chosen = random.choice(mix_scenarios)
            env = make_mixed_env(task, chosen)

        # Run episode
        episode_reward, step_count, avg_per_step, train_metrics = run_episode(agent, env)
        episode_rewards.append(episode_reward)
        episode_steps.append(step_count)

        agent.reset()
        
        # Store episode data
        episode_data.append({
            "episode": episode + 1,
            "reward": float(episode_reward),
            "steps": step_count,
            "epsilon": float(agent.epsilon),
            "buffer_size": len(agent.replay_buffer),
            "avg_reward_per_step": float(avg_per_step),
            "loss": float(train_metrics.get("loss", 0.0)),
            "trained": bool(train_metrics.get("trained", False)),
        })
        
        # Log progress every 10 episodes
        if (episode + 1) % 10 == 0:
            avg_reward_10 = float(np.mean(episode_rewards[-10:]))
            buffer_stats = agent.replay_buffer.get_stats()
            clip_stats = agent.get_training_stats().get("reward_clipping", {})
            state_stats = agent.get_training_stats().get("state_validation", {})
            print_episode_summary(
                episode,
                episodes,
                episode_reward,
                avg_reward_10,
                step_count,
                float(train_metrics.get("epsilon", agent.epsilon)),
                buffer_stats,
            )
            print(f"   Loss: {float(train_metrics.get('loss', 0.0)):.4f}")
            if clip_stats.get("samples", 0) > 0:
                print(
                    "   Reward Clip: "
                    f"adjusted={clip_stats.get('adjusted_count', 0)} "
                    f"({clip_stats.get('adjusted_ratio', 0.0) * 100:.1f}%) "
                    f"min_hits={clip_stats.get('hits_min', 0)} "
                    f"max_hits={clip_stats.get('hits_max', 0)}"
                )
            if state_stats.get("values_checked", 0) > 0:
                print(
                    "   State Clip: "
                    f"values_clipped={state_stats.get('values_clipped', 0)} / "
                    f"{state_stats.get('values_checked', 0)} "
                    f"({state_stats.get('clipped_ratio', 0.0) * 100:.3f}%)"
                )
        
        # Evaluate every N episodes
        if eval_every > 0 and (episode + 1) % eval_every == 0 and episode > 0:
            # True validation pass: deterministic policy, no replay writes.
            prev_training = agent.training
            prev_epsilon = agent.epsilon
            agent.training = False
            agent.epsilon = 0.0

            val_rewards: List[float] = []
            val_steps: List[int] = []
            for _ in range(max(1, validation_episodes)):
                if scenario_mix and task == "task2":
                    val_env = make_mixed_env(task, random.choice(mix_scenarios))
                else:
                    val_env = _make_env(task)
                val_reward, val_step_count = run_eval_episode(agent, val_env)
                val_rewards.append(val_reward)
                val_steps.append(val_step_count)

            agent.training = prev_training
            agent.epsilon = prev_epsilon

            avg_reward_recent = float(np.mean(episode_rewards[-eval_every:]))
            val_avg_reward = float(np.mean(val_rewards))
            val_avg_steps = float(np.mean(val_steps))
            print(f"\n   📊 Evaluation at episode {episode + 1}:")
            print(f"      Train Avg Reward ({eval_every} eps): {avg_reward_recent:+.3f}")
            print(f"      Val Avg Reward ({validation_episodes} eps): {val_avg_reward:+.3f}")
            print(f"      Val Avg Steps: {val_avg_steps:.1f}")
            print_variance_health(val_rewards, "Validation Reward", deterministic_eval=True)

            if val_avg_reward > best_eval_score:
                best_eval_score = val_avg_reward
                patience_counter = 0
                agent.save_model(best_model_path)
                print(f"      🏆 New best model saved: {best_model_path}")
            else:
                patience_counter += 1
                print(
                    "      No improvement: "
                    f"{patience_counter}/{max(0, early_stop_patience)} eval rounds"
                )

            if early_stop_patience > 0 and patience_counter >= early_stop_patience:
                print("\n   ⏹️ Early stopping triggered (validation plateau).")
                break
        
        # Save checkpoint every N episodes
        if checkpoint_every > 0 and (episode + 1) % checkpoint_every == 0 and episode > 0:
            checkpoint_path = save_model.replace(".pth", f".ep{episode + 1}.pth")
            agent.save_model(checkpoint_path)
            if verbose:
                print(f"   💾 Checkpoint saved: {checkpoint_path}")
    
    # Training complete
    print_header("Training Complete")
    
    # Save final model
    os.makedirs(os.path.dirname(save_model), exist_ok=True)
    agent.save_model(save_model)
    print(f"[{format_timestamp()}] 💾 Model saved: {save_model}")
    
    # Calculate final statistics
    final_stats = {
        "task": task,
        "total_episodes": episodes,
        "total_steps": agent.total_steps,
        "final_epsilon": float(agent.epsilon),
        "avg_reward": float(np.mean(episode_rewards)),
        "std_reward": float(np.std(episode_rewards)),
        "max_reward": float(np.max(episode_rewards)),
        "min_reward": float(np.min(episode_rewards)),
        "avg_steps_per_episode": float(np.mean(episode_steps)),
        "buffer_final_size": len(agent.replay_buffer),
        "buffer_stats": agent.replay_buffer.get_stats(),
        "training_stats": agent.get_training_stats(),
    }
    
    # Log statistics
    print(f"\n   Episodes: {episodes}")
    print(f"   Total Steps: {agent.total_steps:,}")
    print(f"   Final Epsilon: {agent.epsilon:.4f}")
    print(f"   Avg Reward: {final_stats['avg_reward']:+.3f} ± {final_stats['std_reward']:.3f}")
    print(f"   Reward Range: [{final_stats['min_reward']:+.3f}, {final_stats['max_reward']:+.3f}]")
    print(f"   Avg Steps/Episode: {final_stats['avg_steps_per_episode']:.1f}")
    print(f"   Buffer Final Size: {final_stats['buffer_final_size']}/{buffer_size}")
    print(f"   Best Eval Reward: {best_eval_score:+.3f}")
    print_variance_health(episode_rewards, "Training Reward")
    clip_stats = final_stats["training_stats"].get("reward_clipping", {})
    state_stats = final_stats["training_stats"].get("state_validation", {})
    if clip_stats.get("samples", 0) > 0:
        print(
            "   Reward Clip Stats: "
            f"adjusted={clip_stats.get('adjusted_count', 0)} / {clip_stats.get('samples', 0)} "
            f"({clip_stats.get('adjusted_ratio', 0.0) * 100:.1f}%)"
        )
    if state_stats.get("values_checked", 0) > 0:
        print(
            "   State Clip Stats: "
            f"clipped={state_stats.get('values_clipped', 0)} / {state_stats.get('values_checked', 0)} "
            f"({state_stats.get('clipped_ratio', 0.0) * 100:.3f}%)"
        )
    
    # Save to JSON
    log_file = os.path.join(log_dir, f"training_log_{task}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(log_file, "w") as f:
        json.dump({
            "final_stats": final_stats,
            "episode_rewards": episode_rewards,
            "episode_steps": episode_steps,
            "episode_data": episode_data,
            "timestamp": format_timestamp(),
        }, f, indent=2)
    
    print(f"   📊 Log saved: {log_file}")
    print("=" * 70)
    
    return agent, final_stats


def evaluate(
    task: str,
    model_path: str,
    episodes: int,
    batch_size: int = 64,
    buffer_size: int = 10000,
    verbose: bool = False,
):
    """
    Evaluate a trained DQN agent.
    
    Args:
        task: Task name
        model_path: Path to saved model
        episodes: Number of evaluation episodes
        batch_size: Batch size (for agent initialization)
        buffer_size: Buffer size (for agent initialization)
        verbose: Print verbose output
    """
    
    print_header("DQN Evaluation")
    print(f"[{format_timestamp()}] Loading model: {model_path}")
    
    # Create environment and load agent
    env = _make_env(task)
    agent = RLAgent(
        task=task,
        training=False,
        model_path=model_path,
        epsilon=0.0,
        epsilon_min=0.0,
        batch_size=batch_size,
        buffer_capacity=buffer_size,
    )
    agent.epsilon = 0.0  # No exploration during eval
    
    # Evaluation loop
    eval_rewards: List[float] = []
    eval_steps: List[int] = []
    
    print_header("Evaluation Progress")
    
    for episode in range(episodes):
        episode_reward, step_count, avg_per_step, _ = run_episode(agent, env)
        eval_rewards.append(episode_reward)
        eval_steps.append(step_count)
        
        agent.reset()
        
        # Print progress every 5 episodes
        if (episode + 1) % 5 == 0 or episode == 0:
            print(f"   Eval {episode + 1:3d}/{episodes}: "
                  f"Reward {episode_reward:+.3f} | Steps {step_count:2d}")
    
    # Evaluation complete
    print_header("Evaluation Summary")
    
    final_stats = {
        "task": task,
        "model_path": model_path,
        "eval_episodes": episodes,
        "avg_reward": float(np.mean(eval_rewards)),
        "std_reward": float(np.std(eval_rewards)),
        "max_reward": float(np.max(eval_rewards)),
        "min_reward": float(np.min(eval_rewards)),
        "avg_steps": float(np.mean(eval_steps)),
    }
    
    print(f"\n   Episodes: {episodes}")
    print(f"   Avg Reward: {final_stats['avg_reward']:+.3f} ± {final_stats['std_reward']:.3f}")
    print(f"   Reward Range: [{final_stats['min_reward']:+.3f}, {final_stats['max_reward']:+.3f}]")
    print(f"   Avg Steps: {final_stats['avg_steps']:.1f}")
    print_variance_health(eval_rewards, "Evaluation Reward")
    print("=" * 70)
    
    return final_stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Train or evaluate DQN agent with experience replay"
    )
    
    # Mode selection
    parser.add_argument(
        "--mode",
        choices=["train", "evaluate"],
        default="train",
        help="Mode: train or evaluate",
    )
    
    # Task and episode settings
    parser.add_argument(
        "--task",
        choices=["task1", "task2", "task3"],
        default="task1",
        help="Task name",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=1000,
        help="Number of episodes",
    )
    
    # Model and logging
    parser.add_argument(
        "--model",
        type=str,
        default="models/dqn_model.pth",
        help="Path to save/load model",
    )
    parser.add_argument(
        "--save-model",
        type=str,
        default=None,
        help="Optional explicit path to save model in train mode",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="logs/training",
        help="Directory to save logs",
    )
    
    # Training hyperparameters
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Batch size for training",
    )
    parser.add_argument(
        "--buffer-size",
        type=int,
        default=10000,
        help="Replay buffer capacity",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.001,
        help="Learning rate",
    )
    parser.add_argument(
        "--gamma",
        type=float,
        default=0.99,
        help="Discount factor",
    )
    parser.add_argument(
        "--epsilon-decay",
        type=float,
        default=0.995,
        help="Epsilon decay rate",
    )
    parser.add_argument(
        "--epsilon-min",
        type=float,
        default=0.01,
        help="Minimum exploration epsilon",
    )
    parser.add_argument(
        "--target-update-freq",
        type=int,
        default=100,
        help="Update target network every N steps",
    )
    
    # Evaluation and checkpointing
    parser.add_argument(
        "--eval-every",
        type=int,
        default=50,
        help="Evaluate every N episodes (0 to disable)",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=100,
        help="Save checkpoint every N episodes (0 to disable)",
    )
    parser.add_argument(
        "--validation-episodes",
        type=int,
        default=5,
        help="Validation episodes per eval cycle",
    )
    parser.add_argument(
        "--early-stop-patience",
        type=int,
        default=0,
        help="Stop after N eval rounds without improvement (0 to disable)",
    )
    parser.add_argument(
        "--best-model",
        type=str,
        default=None,
        help="Path to save best validation model (defaults to model.best.pth)",
    )

    # Scenario mixing and task2 tuned presets
    parser.add_argument(
        "--scenario-mix",
        action="store_true",
        help="Randomize training scenarios per episode (recommended for task2)",
    )
    parser.add_argument(
        "--mix-scenarios",
        type=str,
        default="stable,moderate_risk,high_risk",
        help="Comma-separated internal scenario keys for mixing",
    )
    parser.add_argument(
        "--task2-tuned",
        action="store_true",
        help="Apply recommended task2 training defaults (non-breaking preset)",
    )
    parser.add_argument(
        "--task1-tuned",
        action="store_true",
        help="Apply recommended task1 exploration defaults (non-breaking preset)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume training from --model checkpoint if it exists",
    )
    
    # Misc
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output",
    )
    
    args = parser.parse_args()

    if args.task2_tuned and args.task == "task2":
        if args.epsilon_decay == 0.995:
            args.epsilon_decay = 0.998
        if args.epsilon_min == 0.01:
            args.epsilon_min = 0.05
        if args.buffer_size == 10000:
            args.buffer_size = 20000
        if not args.scenario_mix:
            args.scenario_mix = True

    if args.task1_tuned and args.task == "task1":
        if args.episodes < 1000:
            args.episodes = 1200
        if args.epsilon_decay == 0.995:
            args.epsilon_decay = 0.9995
        if args.epsilon_min == 0.01:
            args.epsilon_min = 0.15
        if args.buffer_size == 10000:
            args.buffer_size = 20000

    model_path = args.save_model or args.model
    mix_scenarios = [s.strip() for s in args.mix_scenarios.split(",") if s.strip()]
    allowed_mix = {"stable", "moderate_risk", "high_risk"}
    invalid_mix = [s for s in mix_scenarios if s not in allowed_mix]
    if invalid_mix:
        raise ValueError(
            "Invalid --mix-scenarios values: "
            f"{invalid_mix}. Allowed: {sorted(allowed_mix)}"
        )
    
    try:
        if args.mode == "train":
            train(
                task=args.task,
                episodes=args.episodes,
                batch_size=args.batch_size,
                buffer_size=args.buffer_size,
                learning_rate=args.learning_rate,
                gamma=args.gamma,
                epsilon_decay=args.epsilon_decay,
                epsilon_min=args.epsilon_min,
                target_update_freq=args.target_update_freq,
                save_model=model_path,
                log_dir=args.log_dir,
                eval_every=args.eval_every,
                checkpoint_every=args.checkpoint_every,
                scenario_mix=args.scenario_mix,
                mix_scenarios=mix_scenarios,
                validation_episodes=args.validation_episodes,
                early_stop_patience=args.early_stop_patience,
                best_model_path=args.best_model,
                resume=args.resume,
                verbose=args.verbose,
            )
        else:  # evaluate
            evaluate(
                task=args.task,
                model_path=args.model,
                episodes=args.episodes,
                batch_size=args.batch_size,
                buffer_size=args.buffer_size,
                verbose=args.verbose,
            )
    except KeyboardInterrupt:
        print("\n⚠️  Training interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
