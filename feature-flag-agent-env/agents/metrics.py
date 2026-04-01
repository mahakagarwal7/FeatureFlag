import json
from typing import Any, Dict, List

import numpy as np


class MetricsTracker:
    """Track agent performance across episodes."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.episodes: List[Dict[str, Any]] = []
        self.total_rewards: List[float] = []
        self.scores: List[float] = []
        self.steps: List[int] = []
        self.final_rollouts: List[float] = []
        self.final_errors: List[float] = []

    def record_episode(self, episode_data: Dict[str, Any]):
        """Record episode results."""
        self.episodes.append(episode_data)
        self.total_rewards.append(float(episode_data["total_reward"]))
        self.scores.append(float(episode_data["score"]))
        self.steps.append(int(episode_data["steps"]))
        self.final_rollouts.append(float(episode_data["final_rollout"]))
        self.final_errors.append(float(episode_data["final_error_rate"]))

    def get_statistics(self) -> Dict[str, Any]:
        """Calculate aggregate statistics."""
        if not self.episodes:
            return {
                "agent_name": self.agent_name,
                "num_episodes": 0,
                "avg_score": 0.0,
                "min_score": 0.0,
                "max_score": 0.0,
                "std_score": 0.0,
                "avg_reward": 0.0,
                "avg_steps": 0.0,
                "avg_final_rollout": 0.0,
                "avg_final_error": 0.0,
            }

        return {
            "agent_name": self.agent_name,
            "num_episodes": len(self.episodes),
            "avg_score": float(np.mean(self.scores)),
            "min_score": float(np.min(self.scores)),
            "max_score": float(np.max(self.scores)),
            "std_score": float(np.std(self.scores)),
            "avg_reward": float(np.mean(self.total_rewards)),
            "avg_steps": float(np.mean(self.steps)),
            "avg_final_rollout": float(np.mean(self.final_rollouts)),
            "avg_final_error": float(np.mean(self.final_errors)),
        }

    def save_to_file(self, filename: str):
        """Save metrics to JSON file."""
        payload = {
            "agent_name": self.agent_name,
            "statistics": self.get_statistics(),
            "episodes": self.episodes,
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def plot_performance(self):
        """Plot score trend over episodes."""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib not installed. Skipping plot.")
            return

        if not self.scores:
            print("No episodes recorded. Nothing to plot.")
            return

        x = list(range(1, len(self.scores) + 1))
        plt.figure(figsize=(10, 5))
        plt.plot(x, self.scores, linewidth=2, color="tab:blue")
        plt.title(f"{self.agent_name} Score per Episode")
        plt.xlabel("Episode")
        plt.ylabel("Score")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()
