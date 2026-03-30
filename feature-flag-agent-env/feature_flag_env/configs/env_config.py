"""
feature_flag_env/configs/env_config.py

Environment configuration and hyperparameters.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EnvironmentConfig:
    """
    Configuration for the Feature Flag Environment.
    """
    
    # Episode settings
    max_steps: int = 50
    default_scenario: str = "stable_feature"
    
    # Simulation settings
    random_seed: Optional[int] = None
    enable_incidents: bool = True
    
    # Reward settings
    reward_scale: float = 1.0
    use_task_specific_rewards: bool = False
    
    # Logging
    verbose: bool = False
    log_to_file: bool = False
    log_dir: str = "logs"
    
    # Performance
    step_timeout: float = 30.0  # seconds
    
    def to_dict(self) -> dict:
        """Convert config to dictionary"""
        return {
            "max_steps": self.max_steps,
            "default_scenario": self.default_scenario,
            "random_seed": self.random_seed,
            "enable_incidents": self.enable_incidents,
            "reward_scale": self.reward_scale,
            "verbose": self.verbose,
        }


# Default configuration
DEFAULT_CONFIG = EnvironmentConfig()

# Task-specific configurations
TASK1_CONFIG = EnvironmentConfig(
    max_steps=10,
    default_scenario="stable_feature",
    enable_incidents=False,
)

TASK2_CONFIG = EnvironmentConfig(
    max_steps=30,
    default_scenario="moderate_risk_feature",
    enable_incidents=True,
)

TASK3_CONFIG = EnvironmentConfig(
    max_steps=50,
    default_scenario="high_risk_feature",
    enable_incidents=True,
)