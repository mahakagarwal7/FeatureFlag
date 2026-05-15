"""
feature_flag_env/tasks/task3_multi_objective.py

Task 3: Multi-Objective Optimization (HARD)

Goal: Maximize revenue while balancing adoption, risk, and system health over 50 steps.

Success Criteria:
- Maximize cumulative revenue
- Maintain system health > 0.7
- Achieve > 80% adoption
- Zero catastrophic failures (error rate < 20% always)
"""

from typing import Dict, Any, Optional
from feature_flag_env.server.feature_flag_environment import FeatureFlagEnvironment
from feature_flag_env.configs.scenario_library import get_scenario


class Task3MultiObjectiveEnvironment(FeatureFlagEnvironment):
    """
    Task 3 Environment: Multi-Objective Optimization
    
    This environment tests agent's ability to balance multiple competing objectives.
    """
    
    def __init__(self):
        # Use high risk scenario for challenging task
        scenario_config = get_scenario("high_risk_feature")
        
        super().__init__(scenario_config=scenario_config)
        
        # Task-specific configuration
        self.task_config = {
            "task_name": "task3_multi_objective",
            "difficulty": "hard",
            "target_rollout": 100.0,
            "target_adoption": 0.80,
            "min_health_score": 0.7,
            "max_error_rate": 0.20,
            "max_steps": 50,
            "description": "Maximize revenue while balancing adoption, risk, and system health",
        }
    
    def reset(self):
        """
        Reset environment for Task 3.
        Ensures challenging conditions for multi-objective optimization.
        """
        # Override scenario with high risk one
        self.scenario_config = get_scenario("high_risk_feature")
        
        # Call parent reset
        observation = super().reset()
        
        # Override max_steps for this task
        if self._state:
            self._state.max_steps = self.task_config["max_steps"]
            self._state.scenario_name = "task3_high_risk"
            self._state.difficulty = "hard"
        
        return observation


def make_task3_environment() -> Task3MultiObjectiveEnvironment:
    """
    Factory function to create Task 3 environment.
    
    Returns:
        Task3MultiObjectiveEnvironment: Configured environment for Task 3
    """
    return Task3MultiObjectiveEnvironment()