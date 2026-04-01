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
    incident_probability_multiplier: float = 1.0
    
    # Reward settings
    reward_scale: float = 1.0
    use_task_specific_rewards: bool = False
    reward_function: str = "default"
    
    # Logging
    verbose: bool = False
    log_to_file: bool = False
    log_dir: str = "logs"
    log_level: str = "INFO"
    
    # Performance
    step_timeout: float = 30.0  # seconds
    enable_caching: bool = True

    # API optimization
    cache_api_responses: bool = True
    api_cache_ttl: int = 300
    
    def to_dict(self) -> dict:
        """Convert config to dictionary"""
        return {
            "max_steps": self.max_steps,
            "default_scenario": self.default_scenario,
            "random_seed": self.random_seed,
            "enable_incidents": self.enable_incidents,
            "incident_probability_multiplier": self.incident_probability_multiplier,
            "reward_scale": self.reward_scale,
            "use_task_specific_rewards": self.use_task_specific_rewards,
            "reward_function": self.reward_function,
            "verbose": self.verbose,
            "log_to_file": self.log_to_file,
            "log_dir": self.log_dir,
            "log_level": self.log_level,
            "step_timeout": self.step_timeout,
            "enable_caching": self.enable_caching,
            "cache_api_responses": self.cache_api_responses,
            "api_cache_ttl": self.api_cache_ttl,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EnvironmentConfig":
        """Create config from dictionary"""
        return cls(**data)


# Default configuration
DEFAULT_CONFIG = EnvironmentConfig()

# Task-specific configurations
TASK1_CONFIG = EnvironmentConfig(
    max_steps=10,
    default_scenario="stable_feature",
    enable_incidents=False,
    reward_function="default",
)

TASK2_CONFIG = EnvironmentConfig(
    max_steps=30,
    default_scenario="moderate_risk_feature",
    enable_incidents=True,
    reward_function="default",
)

TASK3_CONFIG = EnvironmentConfig(
    max_steps=50,
    default_scenario="high_risk_feature",
    enable_incidents=True,
    reward_function="default",
)