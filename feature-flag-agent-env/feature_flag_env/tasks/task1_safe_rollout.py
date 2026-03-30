"""
feature_flag_env/tasks/task1_safe_rollout.py

Task 1: Safe Small Rollout (EASY)

Goal: Gradually rollout a feature from 0% to 25% without exceeding error thresholds.

Success Criteria:
- Reach 25% rollout
- Keep error rate < 5%
- Complete within 10 steps
- No rollbacks
"""

from typing import Dict, Any, Optional
from feature_flag_env.server.feature_flag_environment import FeatureFlagEnvironment
from feature_flag_env.configs.scenario_library import get_scenario


class Task1SafeRolloutEnvironment(FeatureFlagEnvironment):
    """
    Task 1 Environment: Safe Small Rollout
    
    This environment is configured specifically for Task 1 requirements.
    """
    
    def __init__(self):
        # Use stable scenario for easy task
        scenario_config = get_scenario("stable_feature")
        
        super().__init__(scenario_config=scenario_config)
        
        # Task-specific configuration
        self.task_config = {
            "task_name": "task1_safe_rollout",
            "difficulty": "easy",
            "target_rollout": 25.0,
            "max_error_rate": 0.05,
            "max_steps": 10,
            "description": "Safely rollout a feature from 0% to 25% without exceeding error thresholds",
        }
    
    def reset(self):
        """
        Reset environment for Task 1.
        Ensures stable conditions for easy task.
        """
        # Override scenario with stable one
        self.scenario_config = get_scenario("stable_feature")
        
        # Call parent reset
        observation = super().reset()
        
        # Override max_steps for this task
        if self._state:
            self._state.max_steps = self.task_config["max_steps"]
            self._state.scenario_name = "task1_stable"
            self._state.difficulty = "easy"
        
        return observation


def make_task1_environment() -> Task1SafeRolloutEnvironment:
    """
    Factory function to create Task 1 environment.
    
    Returns:
        Task1SafeRolloutEnvironment: Configured environment for Task 1
    """
    return Task1SafeRolloutEnvironment()