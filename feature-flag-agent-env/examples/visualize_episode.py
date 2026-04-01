import argparse
import os
import sys
from typing import Any, Dict, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
	sys.path.insert(0, PROJECT_ROOT)


def visualize_episode(trajectory: List[Dict[str, Any]]):
	"""
	Visualize a single episode trajectory.

	Creates a multi-panel plot showing rollout, errors, latency, health,
	rewards, and action distribution over the episode.
	"""
	import matplotlib.pyplot as plt

	if not trajectory:
		print("No trajectory data to visualize.")
		return

	steps = list(range(1, len(trajectory) + 1))
	rollouts = [step["observation"].current_rollout_percentage for step in trajectory]
	errors = [step["observation"].error_rate * 100 for step in trajectory]
	latencies = [step["observation"].latency_p99_ms for step in trajectory]
	health = [step["observation"].system_health_score for step in trajectory]
	rewards = [step["reward"] for step in trajectory]
	actions = [step["action"].action_type for step in trajectory]

	fig, axes = plt.subplots(3, 2, figsize=(12, 10))

	axes[0, 0].plot(steps, rollouts, "b-", linewidth=2)
	axes[0, 0].set_title("Rollout Percentage")
	axes[0, 0].set_xlabel("Step")
	axes[0, 0].set_ylabel("Rollout %")
	axes[0, 0].grid(True)

	axes[0, 1].plot(steps, errors, "r-", linewidth=2)
	axes[0, 1].axhline(y=5, color="orange", linestyle="--", label="5% threshold")
	axes[0, 1].set_title("Error Rate")
	axes[0, 1].set_xlabel("Step")
	axes[0, 1].set_ylabel("Error %")
	axes[0, 1].legend()
	axes[0, 1].grid(True)

	axes[1, 0].plot(steps, latencies, "g-", linewidth=2)
	axes[1, 0].axhline(y=200, color="orange", linestyle="--", label="200ms threshold")
	axes[1, 0].set_title("Latency (p99)")
	axes[1, 0].set_xlabel("Step")
	axes[1, 0].set_ylabel("Latency (ms)")
	axes[1, 0].legend()
	axes[1, 0].grid(True)

	axes[1, 1].plot(steps, health, color="purple", linewidth=2)
	axes[1, 1].axhline(y=0.7, color="orange", linestyle="--", label="0.7 threshold")
	axes[1, 1].set_title("System Health Score")
	axes[1, 1].set_xlabel("Step")
	axes[1, 1].set_ylabel("Health Score")
	axes[1, 1].legend()
	axes[1, 1].grid(True)

	axes[2, 0].plot(steps, rewards, color="orange", linewidth=2)
	axes[2, 0].axhline(y=0, color="gray", linestyle="-", linewidth=0.5)
	axes[2, 0].set_title("Reward per Step")
	axes[2, 0].set_xlabel("Step")
	axes[2, 0].set_ylabel("Reward")
	axes[2, 0].grid(True)

	action_counts = {}
	for action in actions:
		action_counts[action] = action_counts.get(action, 0) + 1
	axes[2, 1].bar(action_counts.keys(), action_counts.values())
	axes[2, 1].set_title("Action Distribution")
	axes[2, 1].set_xlabel("Action Type")
	axes[2, 1].set_ylabel("Count")
	axes[2, 1].tick_params(axis="x", rotation=45)

	plt.tight_layout()
	plt.savefig("episode_visualization.png", dpi=300)
	print("Saved visualization to episode_visualization.png")
	plt.show()


def main():
	parser = argparse.ArgumentParser(description="Visualize one feature-flag episode")
	parser.add_argument("--agent", type=str, default="baseline", choices=["baseline", "llm", "hybrid", "rl"])
	parser.add_argument("--task", type=str, default="task1", choices=["task1", "task2", "task3"])
	args = parser.parse_args()

	from agents.factory import get_agent
	from inference import EnvironmentClient, run_episode

	agent = get_agent(args.agent)
	env_client = EnvironmentClient(task=args.task)
	result = run_episode(agent, env_client, task=args.task)
	visualize_episode(result["trajectory"])


if __name__ == "__main__":
	main()
