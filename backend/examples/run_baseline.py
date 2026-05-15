import argparse
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
	sys.path.insert(0, PROJECT_ROOT)

from agents.baseline_agent import BaselineAgent
from inference import EnvironmentClient, run_episode


def main():
	parser = argparse.ArgumentParser(description="Run baseline agent episodes")
	parser.add_argument("--episodes", type=int, default=5)
	parser.add_argument("--task", type=str, default="task1", choices=["task1", "task2", "task3"])
	parser.add_argument("--debug", action="store_true")
	args = parser.parse_args()

	agent = BaselineAgent()
	env_client = EnvironmentClient(task=args.task)

	scores = []
	for i in range(args.episodes):
		print(f"\n--- Baseline Episode {i + 1}/{args.episodes} ---")
		result = run_episode(agent, env_client, task=args.task, debug=args.debug)
		scores.append(result["score"])

	avg = sum(scores) / len(scores) if scores else 0.0
	print(f"\nBaseline finished. Avg score: {avg:.3f}")


if __name__ == "__main__":
	main()
