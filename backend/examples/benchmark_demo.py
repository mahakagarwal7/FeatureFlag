"""
examples/benchmark_demo.py

Demonstrates the Benchmarking Analytics Layer.
Compares a simulated deployment against FinTech Enterprise standards.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from feature_flag_env.server.feature_flag_environment import make_environment
from feature_flag_env.models import FeatureFlagAction


def main():
    bench_config = {"industry": "fintech", "company_size": "enterprise"}

    env = make_environment(
        scenario_config={"scenario_name": "high_risk"},
        benchmarking_config=bench_config,
    )

    print(f"--- Benchmarking Demo: {bench_config['industry'].upper()} {bench_config['company_size'].upper()} ---")

    obs = env.reset()

    for step in range(1, 4):
        target_pct = step * 20.0
        action = FeatureFlagAction(
            action_type="INCREASE_ROLLOUT",
            target_percentage=target_pct,
            reason="Advancing rollout for benchmarking test",
        )

        response = env.step(action)
        obs = response.observation

        bench = env.analytics.get("benchmark", {})
        print(f"\nStep {step}: Rollout={obs.current_rollout_percentage}%")
        print(f"  Metrics: Error={obs.error_rate:.4f}, Latency={obs.latency_p99_ms:.1f}ms")
        print(f"  Benchmark: {bench.get('comparison', 'N/A')}")
        print(f"  Percentile: {bench.get('percentile', 0)*100:.1f}%")
        for rec in bench.get("recommendations", []):
            print(f"    → {rec}")


if __name__ == "__main__":
    main()
