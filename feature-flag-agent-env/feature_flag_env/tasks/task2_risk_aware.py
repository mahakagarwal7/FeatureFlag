"""
feature_flag_env/tasks/task2_risk_aware.py

Task 2: Risk-Aware Scaling (MEDIUM)

Goal: Scale to 75% rollout while responding to simulated incidents.

Success Criteria:
- Reach 75% final rollout
- Detect and respond to incidents (decrease when errors spike)
- Recover after incidents
- Maintain latency < 200ms
"""

from typing import Dict, Any, Optional
from feature_flag_env.server.feature_flag_environment import FeatureFlagEnvironment
from feature_flag_env.configs.scenario_library import get_scenario


class Task2RiskAwareEnvironment(FeatureFlagEnvironment):
    """
    Task 2 Environment: Risk-Aware Scaling
    
    This environment includes incident zones to test agent's risk awareness.
    """
    
    def __init__(self):
        # Use moderate risk scenario with incident zone
        scenario_config = get_scenario("moderate_risk_feature")
        
        super().__init__(scenario_config=scenario_config)
        
        # Task-specific configuration
        self.task_config = {
            "task_name": "task2_risk_aware",
            "difficulty": "medium",
            "target_rollout": 75.0,
            "max_error_rate": 0.10,
            "max_steps": 30,
            "incident_zone": {"min": 40, "max": 50},
            "description": "Scale to 75% rollout while responding to simulated incidents",
        }
    
    def reset(self):
        """
        Reset environment for Task 2.
        Ensures incident zone is active for testing risk response.
        """
        # Override scenario with moderate risk one
        self.scenario_config = get_scenario("moderate_risk_feature")
        
        # Call parent reset
        observation = super().reset()
        
        # Override max_steps for this task
        if self._state:
            self._state.max_steps = self.task_config["max_steps"]
            self._state.scenario_name = "task2_moderate_risk"
            self._state.difficulty = "medium"
        
        return observation


def make_task2_environment() -> Task2RiskAwareEnvironment:
    """
    Factory function to create Task 2 environment.
    
    Returns:
        Task2RiskAwareEnvironment: Configured environment for Task 2
    """
    return Task2RiskAwareEnvironment()