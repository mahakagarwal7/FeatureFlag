"""
feature_flag_env/server/feature_flag_environment.py

Main Environment Class (OpenEnv Compliant)
"""

from typing import Dict, Any, Optional
from feature_flag_env.models import (
    FeatureFlagAction,
    FeatureFlagObservation,
    FeatureFlagState,
    StepResponse,
)
from feature_flag_env.server.simulation_engine import FeatureFlagSimulator
from feature_flag_env.utils.reward_functions import (
    calculate_reward,
    calculate_reward_task1,
    calculate_reward_task2,
    calculate_reward_task3,
)
import uuid
import random


class FeatureFlagEnvironment:
    def __init__(self, scenario_config: Optional[Dict[str, Any]] = None):
        self.scenario_library = {
            "stable": {
                "name": "stable_feature",
                "base_error_rate": 0.01,
                "error_variance": 0.002,
                "latency_per_10pct_rollout": 3.0,
                "adoption_speed": 0.15,
                "revenue_per_user": 0.10,
                "total_users": 10000,
                "incident_zones": [],
            },
            "moderate_risk": {
                "name": "moderate_risk_feature",
                "base_error_rate": 0.03,
                "error_variance": 0.01,
                "latency_per_10pct_rollout": 8.0,
                "adoption_speed": 0.10,
                "revenue_per_user": 0.20,
                "total_users": 10000,
                "incident_zones": [
                    {"min": 40, "max": 50, "probability": 0.25, "spike": 0.12}
                ],
            },
            "high_risk": {
                "name": "high_risk_feature",
                "base_error_rate": 0.05,
                "error_variance": 0.02,
                "latency_per_10pct_rollout": 15.0,
                "adoption_speed": 0.08,
                "revenue_per_user": 0.30,
                "total_users": 10000,
                "incident_zones": [
                    {"min": 25, "max": 35, "probability": 0.30, "spike": 0.15},
                    {"min": 55, "max": 65, "probability": 0.25, "spike": 0.12},
                ],
            },
        }

        self.simulator: Optional[FeatureFlagSimulator] = None
        
        self._state: Optional[FeatureFlagState] = None
        self.previous_observation: Optional[FeatureFlagObservation] = None
        self.scenario_config = scenario_config

   
    def reset(self) -> FeatureFlagObservation:
        if self.scenario_config:
            # Support passing either a full scenario config or a task name.
            if "scenario_name" in self.scenario_config:
                scenario_name = self.scenario_config["scenario_name"]
                config = self.scenario_library.get(scenario_name, self.scenario_library["stable"])
            elif "task_name" in self.scenario_config:
                task_to_scenario = {
                    "task1": "stable",
                    "task2": "moderate_risk",
                    "task3": "high_risk",
                }
                scenario_name = task_to_scenario.get(self.scenario_config["task_name"], "stable")
                config = self.scenario_library[scenario_name]
            else:
                config = self.scenario_config
                scenario_name = config.get("name", "custom")
        else:
            scenario_name = random.choice(list(self.scenario_library.keys()))
            config = self.scenario_library[scenario_name]

        seed = random.randint(0, 10000)
        self.simulator = FeatureFlagSimulator(config, seed=seed)

       
        self._state = FeatureFlagState(
            episode_id=str(uuid.uuid4()),
            step_count=0,
            max_steps={
                "easy": 10,
                "medium": 30,
                "hard": 50,
            }.get(self._get_difficulty(scenario_name), 50),
            total_reward=0.0,
            rollout_history=[],
            action_history=[],
            done=False,
            scenario_name=scenario_name,
            difficulty=self._get_difficulty(scenario_name),
        )

        initial_metrics = self.simulator.step(target_rollout=0.0)

        observation = FeatureFlagObservation(
            current_rollout_percentage=0.0,
            error_rate=initial_metrics["error_rate"],
            latency_p99_ms=initial_metrics["latency_p99_ms"],
            user_adoption_rate=initial_metrics["user_adoption_rate"],
            revenue_impact=initial_metrics["revenue_impact"],
            system_health_score=initial_metrics["system_health_score"],
            active_users=initial_metrics["active_users"],
            feature_name=f"feature_{self._state.episode_id[:8]}",
            time_step=0,
            reward=None,
            done=False,
        )

        self.previous_observation = observation
        return observation

    
    def step(self, action: FeatureFlagAction) -> StepResponse:
        if not 0.0 <= action.target_percentage <= 100.0:
            raise ValueError("target_percentage must be between 0 and 100")

       
        if self._state is None or self._state.done:
            raise ValueError("Episode done. Call reset()")

        if self.simulator is None:
            raise ValueError("Simulator not initialized. Call reset()")

        old_obs = self.previous_observation

        new_metrics = self.simulator.step(action.target_percentage)

        
        self._state.add_step(action, reward=0.0)

        observation = FeatureFlagObservation(
            current_rollout_percentage=action.target_percentage,
            error_rate=new_metrics["error_rate"],
            latency_p99_ms=new_metrics["latency_p99_ms"],
            user_adoption_rate=new_metrics["user_adoption_rate"],
            revenue_impact=new_metrics["revenue_impact"],
            system_health_score=new_metrics["system_health_score"],
            active_users=new_metrics["active_users"],
            feature_name=old_obs.feature_name,
            time_step=self._state.step_count,
            reward=None,
            done=False,
        )

        
        reward = calculate_reward(old_obs, observation, action)
        # Task-aligned reward:
        # The graders evaluate task-specific objectives, so the training reward should
        # be consistent with the task difficulty of the chosen scenario.
        if self._state.difficulty == "easy":
            reward = calculate_reward_task1(old_obs, observation, action)
        elif self._state.difficulty == "medium":
            reward = calculate_reward_task2(old_obs, observation, action)
        elif self._state.difficulty == "hard":
            reward = calculate_reward_task3(old_obs, observation, action)
        
       
        self._state.total_reward += reward

       
        done = self._check_done(observation, action)
        self._state.done = done
        observation.done = done
        observation.reward = reward

        self.previous_observation = observation

        return StepResponse(
            observation=observation,
            reward=reward,
            done=done,
            info={
                "scenario_name": self._state.scenario_name,
                "difficulty": self._state.difficulty,
                "step_count": self._state.step_count,
                "total_reward": self._state.total_reward,
            },
        )

   
    def state(self) -> FeatureFlagState:
        """
        Return current episode state.
        This is the METHOD that OpenEnv expects.
        """
       
        if self._state is None:
            raise ValueError("Call reset() first")
        return self._state

    
    def _get_difficulty(self, scenario_name: str) -> str:
        return {
            "stable": "easy",
            "moderate_risk": "medium",
            "high_risk": "hard",
        }.get(scenario_name, "medium")

    def _check_done(self, observation, action) -> bool:
      
        if self._state.step_count >= self._state.max_steps:
            return True

        if observation.error_rate > 0.25:
            return True

        if action.target_percentage >= 100.0:
            return True

        return False



def make_environment(scenario_config: Optional[Dict[str, Any]] = None):
    return FeatureFlagEnvironment(scenario_config)