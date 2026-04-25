"""
simulate_conflicts.py

Demonstrates the enhanced multi-stakeholder feedback system,
showing how the FeedbackVector captures disagreement and how
the BeliefTracker identifies trends.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from feature_flag_env.stakeholders import StakeholderPanel, ConflictScenarios
from feature_flag_env.models import FeatureFlagObservation

def run_scenario(name: str, observations: list[FeatureFlagObservation]):
    print("=" * 60)
    print(f"🚀 SCENARIO: {name}")
    print("=" * 60)
    
    panel = StakeholderPanel()
    panel.reset()
    
    for i, obs in enumerate(observations):
        print(f"\n{'='*20} Step {i} {'='*20}")
        print(f"Metrics: Rollout {obs.current_rollout_percentage}%, Error: {obs.error_rate:.2%}, Users: {obs.active_users}")
        
        # Get structured feedback vector
        vector = panel.get_feedback_vector(obs)
        print("\n" + vector.to_prompt_section())
        
        # Display belief tracker trends
        summary = panel.belief_tracker.summary()
        trends = summary["satisfaction_trends"]
        print(f"\nBelief Trends:")
        print(f"  - DevOps:   {trends['devops']}")
        print(f"  - Product:  {trends['product']}")
        print(f"  - Customer: {trends['customer_success']}")
        print(f"  - Conflict: {summary['conflict_trend']} (Level: {summary['latest_conflict']:.2f})")

if __name__ == "__main__":
    run_scenario("Speed vs Stability", ConflictScenarios.speed_vs_stability())
    run_scenario("Growth vs Quality", ConflictScenarios.growth_vs_quality())
    run_scenario("Total Conflict", ConflictScenarios.total_conflict())
