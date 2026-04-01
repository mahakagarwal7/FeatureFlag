import argparse
import glob
import json
import os
from typing import Dict, List


def _load_metric_files(log_dir: str) -> List[Dict]:
    metric_files = sorted(glob.glob(os.path.join(log_dir, "*_metrics.json")))
    payloads = []
    for path in metric_files:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["_path"] = path
            payloads.append(data)
    return payloads


def visualize_training(log_dir: str, save_path: str = "training_comparison.png"):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed. Install with: pip install matplotlib")
        return

    payloads = _load_metric_files(log_dir)
    if not payloads:
        print(f"No metrics files found in {log_dir}")
        return

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))

    for payload in payloads:
        agent = payload.get("agent_name", "unknown")
        episodes = payload.get("episodes", [])
        stats = payload.get("statistics", {})

        if episodes:
            x = [ep.get("episode", i + 1) for i, ep in enumerate(episodes)]
            scores = [float(ep.get("score", 0.0)) for ep in episodes]
            rewards = [float(ep.get("total_reward", 0.0)) for ep in episodes]
            steps = [float(ep.get("steps", 0.0)) for ep in episodes]
            errors = [float(ep.get("final_error_rate", 0.0)) * 100.0 for ep in episodes]

            axes[0, 0].plot(x, scores, marker="o", linewidth=1.8, label=agent)
            axes[0, 1].plot(x, rewards, marker="o", linewidth=1.8, label=agent)
            axes[1, 0].plot(x, steps, marker="o", linewidth=1.8, label=agent)
            axes[1, 1].plot(x, errors, marker="o", linewidth=1.8, label=agent)
        else:
            print(f"Warning: {agent} has no per-episode data in {payload['_path']}")
            # Fall back to a single-point visualization from statistics.
            axes[0, 0].scatter([1], [float(stats.get("avg_score", 0.0))], label=agent)
            axes[0, 1].scatter([1], [float(stats.get("avg_reward", 0.0))], label=agent)
            axes[1, 0].scatter([1], [float(stats.get("avg_steps", 0.0))], label=agent)
            axes[1, 1].scatter([1], [float(stats.get("avg_final_error", 0.0)) * 100.0], label=agent)

    axes[0, 0].set_title("Score per Episode")
    axes[0, 1].set_title("Reward per Episode")
    axes[1, 0].set_title("Steps per Episode")
    axes[1, 1].set_title("Final Error Rate per Episode")

    axes[0, 0].set_ylabel("Score")
    axes[0, 1].set_ylabel("Reward")
    axes[1, 0].set_ylabel("Steps")
    axes[1, 1].set_ylabel("Error %")

    for ax in axes.flatten():
        ax.set_xlabel("Episode")
        ax.grid(True, alpha=0.3)
        ax.legend()

    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    print(f"Saved training visualization to {save_path}")
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize training logs from metrics JSON files")
    parser.add_argument("--log-dir", type=str, default="logs/training")
    parser.add_argument("--save-path", type=str, default="training_comparison.png")
    args = parser.parse_args()

    visualize_training(log_dir=args.log_dir, save_path=args.save_path)
