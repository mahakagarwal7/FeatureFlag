import argparse
import os
import sys
from typing import List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agents.metrics import MetricsTracker
from inference import EnvironmentClient, run_episode


def _build_agent(agent_name: str, task: str):
    if agent_name == "rl":
        from agents.rl_agent import RLAgent

        return RLAgent(task=task, training=False, epsilon=0.0, epsilon_min=0.0)

    from agents.factory import get_agent

    return get_agent(agent_name)


def _is_llm_active(agent) -> bool:
    # LLM-backed agents expose use_baseline=False only when API usage is active.
    if hasattr(agent, "use_baseline"):
        return not bool(getattr(agent, "use_baseline"))
    if hasattr(agent, "llm") and hasattr(agent.llm, "use_baseline"):
        return not bool(getattr(agent.llm, "use_baseline"))
    return False


def run_comparison(agent_names: List[str], episodes: int, task: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    for agent_name in agent_names:
        print("\n" + "=" * 70)
        print(f"Running agent: {agent_name}")
        print("=" * 70)

        agent = _build_agent(agent_name, task)
        tracker = MetricsTracker(agent_name=agent_name)
        env_client = EnvironmentClient(task=task)

        api_calls = 0
        for ep in range(episodes):
            print(f"\nEpisode {ep + 1}/{episodes}")
            result = run_episode(agent, env_client, task=task)

            if _is_llm_active(agent):
                api_calls += result["steps"]

            tracker.record_episode(
                {
                    "episode": ep + 1,
                    "steps": result["steps"],
                    "total_reward": result["total_reward"],
                    "final_rollout": result["final_rollout"],
                    "final_error_rate": result["final_error_rate"],
                    "score": result["score"],
                }
            )

            if hasattr(agent, "decay_epsilon"):
                agent.decay_epsilon()
            if hasattr(agent, "reset"):
                agent.reset()

        stats = tracker.get_statistics()
        stats_path = os.path.join(output_dir, f"{agent_name}_metrics.json")
        tracker.save_to_file(stats_path)

        print("\nSummary")
        print(f"  Avg score: {stats['avg_score']:.3f}")
        print(f"  Avg reward: {stats['avg_reward']:.3f}")
        print(f"  Avg steps: {stats['avg_steps']:.2f}")
        print(f"  Avg final rollout: {stats['avg_final_rollout']:.2f}%")
        print(f"  Avg final error: {stats['avg_final_error'] * 100:.2f}%")
        print(f"  Metrics file: {stats_path}")

        if agent_name in {"llm", "hybrid"}:
            per_ep = api_calls / max(episodes, 1)
            print(f"  Total API calls (estimated): {api_calls} ({per_ep:.2f} per episode)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare multiple agents on the same task")
    parser.add_argument(
        "--agents",
        nargs="+",
        default=["baseline", "llm", "rl", "hybrid"],
        choices=["baseline", "llm", "rl", "hybrid"],
        help="Agent names to compare",
    )
    parser.add_argument("--episodes", type=int, default=10, help="Episodes per agent")
    parser.add_argument("--task", type=str, default="task3", choices=["task1", "task2", "task3"])
    parser.add_argument("--output-dir", type=str, default="logs/training")

    args = parser.parse_args()
    run_comparison(args.agents, args.episodes, args.task, args.output_dir)
