"""
feature_flag_env/server/feature_flag_environment.py

Main Environment Class (OpenEnv Compliant)
"""

from typing import Dict, Any, Optional, List
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
from feature_flag_env.utils.extended_rewards import calculate_extended_reward
from feature_flag_env.stakeholders import StakeholderPanel, StakeholderRole
from feature_flag_env.missions import MissionTracker, get_mission
from feature_flag_env.tools.tool_manager import ToolManager
from feature_flag_env.tools.tool_interface import ToolCallRequest
from feature_flag_env.tools.mock_adapters import MockGitHubTool, MockSlackTool
from feature_flag_env.engine_plugins import ChaosEngine, ApprovalWorkflow
from feature_flag_env.historical_patterns import CustomerProfile, PatternAnalyzer, DeploymentPattern
from feature_flag_env.anomaly_detection import AnomalyDetector
from feature_flag_env.benchmarking import BenchmarkEngine
import uuid
import random


class FeatureFlagEnvironment:
    def __init__(self, scenario_config: Optional[Dict[str, Any]] = None,
                 stakeholders_enabled: bool = False,
                 mission_config: Optional[str] = None,
                 tools_enabled: bool = False,
                 tool_manager: Optional[ToolManager] = None,
                 chaos_enabled: bool = False,
                 hitl_enabled: bool = False,
                 benchmarking_config: Optional[Dict[str, str]] = None):
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

        # --- Extended features ---
        self.stakeholders_enabled = stakeholders_enabled
        self._stakeholder_panel: Optional[StakeholderPanel] = None

        self.mission_config = mission_config  # mission name string
        self._mission_tracker: Optional[MissionTracker] = None

        # --- Tool integration ---
        self.tools_enabled = tools_enabled
        self._tool_manager: Optional[ToolManager] = tool_manager

        # --- Chaos & HITL plugins ---
        self.chaos_enabled = chaos_enabled
        self.hitl_enabled = hitl_enabled
        self._chaos_engine: Optional[ChaosEngine] = None
        self._approval_workflow: Optional[ApprovalWorkflow] = None

        # --- Historical Pattern Learning ---
        self._customer_profile: Optional[CustomerProfile] = None
        self._pattern_analyzer: Optional[PatternAnalyzer] = None
        self._anomaly_detector = AnomalyDetector()
        self._extra_context_data: Dict[str, Any] = {}

        # --- Benchmarking Analytics ---
        self.benchmarking_config = benchmarking_config
        self._benchmark_engine: Optional[BenchmarkEngine] = None
        self.analytics: Dict[str, Any] = {}

   
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
        elif self.mission_config:
            # Mission mode: use the mission's scenario
            mission = get_mission(self.mission_config)
            scenario_name = mission.scenario_name
            config = self.scenario_library.get(scenario_name, self.scenario_library["stable"])
        else:
            scenario_name = random.choice(list(self.scenario_library.keys()))
            config = self.scenario_library[scenario_name]

        seed = random.randint(0, 10000)
        self.simulator = FeatureFlagSimulator(config, seed=seed)

        # Determine max_steps: mission total or difficulty-based
        if self.mission_config:
            mission = get_mission(self.mission_config)
            max_steps = mission.total_max_steps()
        else:
            max_steps = {
                "easy": 10,
                "medium": 30,
                "hard": 50,
            }.get(self._get_difficulty(scenario_name), 50)

        self._state = FeatureFlagState(
            episode_id=str(uuid.uuid4()),
            step_count=0,
            max_steps=max_steps,
            total_reward=0.0,
            rollout_history=[],
            action_history=[],
            done=False,
            scenario_name=scenario_name,
            difficulty=self._get_difficulty(scenario_name),
        )

        # --- Initialize extended features ---
        if self.stakeholders_enabled:
            self._stakeholder_panel = StakeholderPanel()
            self._stakeholder_panel.reset()

        if self.mission_config:
            mission = get_mission(self.mission_config)
            self._mission_tracker = MissionTracker(mission)
            self._mission_tracker.reset()

        # --- Initialize tool manager ---
        if self.tools_enabled:
            if self._tool_manager is None:
                self._tool_manager = ToolManager()
                self._tool_manager.register(MockGitHubTool())
                self._tool_manager.register(MockSlackTool())
            self._tool_manager.reset()

        # --- Initialize Chaos & HITL ---
        if self.chaos_enabled:
            if self._chaos_engine is None:
                self._chaos_engine = ChaosEngine()
            self._chaos_engine.reset()
        
        if self.hitl_enabled:
            if self._approval_workflow is None:
                self._approval_workflow = ApprovalWorkflow()
            self._approval_workflow.reset()
        
        if self._anomaly_detector:
            self._anomaly_detector.reset()
        self._extra_context_data = {}

        # --- Reset Benchmarking ---
        if self.benchmarking_config:
            self._benchmark_engine = BenchmarkEngine(
                industry=self.benchmarking_config.get("industry", "saas"),
                company_size=self.benchmarking_config.get("company_size", "mid-market")
            )
        else:
            self._benchmark_engine = None
        self.analytics = {}

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

        # Populate extended observation fields at reset
        observation = self._populate_extended_obs(observation)
        self._update_analytics(observation)
        
        self._state.observation_history.append(observation)

        self.previous_observation = observation
        return observation

    
    def step(self, action: FeatureFlagAction) -> StepResponse:
        if action.action_type != "TOOL_CALL" and not 0.0 <= action.target_percentage <= 100.0:
            raise ValueError("target_percentage must be between 0 and 100")

       
        if self._state is None or self._state.done:
            raise ValueError("Episode done. Call reset()")

        if self.simulator is None:
            raise ValueError("Simulator not initialized. Call reset()")

        # --- Feature 3: Phase Constraints ---
        if self._mission_tracker and self._mission_tracker.current_phase:
            phase = self._mission_tracker.current_phase
            
            # Constraint 1: Rejected Actions
            if action.action_type not in phase.allowed_actions:
                self._state.add_step(action, reward=-1.0)
                obs_out = self.previous_observation
                obs_out.reward = -1.0
                obs_out.time_step = self._state.step_count
                obs_out = self._populate_extended_obs(obs_out)
                self._state.observation_history.append(obs_out)
                return StepResponse(
                    observation=obs_out,
                    reward=-1.0,
                    done=self._check_done(obs_out, action),
                    info={"error": f"Action {action.action_type} is not allowed in phase '{phase.name}'"}
                )
            
            # Constraint 2: Skip Prevention (Clamp Target)
            if action.action_type in {"INCREASE_ROLLOUT", "FULL_ROLLOUT"}:
                if action.target_percentage > phase.target_rollout_max:
                    action.target_percentage = float(phase.target_rollout_max)
                    action.reason += f" | Clamped to phase exit bounds ({phase.target_rollout_max}%)"

            # Constraint 3: HITL Approval
            if self.hitl_enabled and self._approval_workflow:
                # If we are crossing a phase boundary, request approval if not already approved
                next_phase_trigger = action.target_percentage >= phase.target_rollout_max
                if next_phase_trigger and self._approval_workflow.status == "NONE":
                    self._approval_workflow.request_approval(phase.name, f"Transition from {phase.name} requested")
                
                if self._approval_workflow.status == "PENDING":
                    # Block progress: force MAINTAIN at the boundary
                    action.action_type = "MAINTAIN"
                    action.target_percentage = float(phase.target_rollout_max)
                    action.reason += " | BLOCKED BY PENDING APPROVAL"
                elif self._approval_workflow.status == "REJECTED":
                    action.action_type = "ROLLBACK"
                    action.target_percentage = 0.0
                    action.reason += " | REJECTED BY STAKEHOLDERS"
                    self._approval_workflow.reset() # Allow re-requesting after rollback

        # --- Process Chaos Monkey ---
        chaos_incident = None
        if self.chaos_enabled and self._chaos_engine is not None:
            chaos_incident = self._chaos_engine.step()

        # --- Handle TOOL_CALL action type ---
        if action.action_type == "TOOL_CALL":
            res = self._handle_tool_call(action)
            if res and chaos_incident:
                res.observation.chaos_incident = chaos_incident
            return res

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

        # --- Collect stakeholder feedback ---
        stakeholder_sentiments = {}
        phase_advanced = False
        phase_progress_value = 0.0
        phase_reward_weight = 1.0

        if self._stakeholder_panel is not None:
            feedbacks = self._stakeholder_panel.get_all_feedback(observation)
            stakeholder_sentiments = {
                role.value: self._stakeholder_panel.__dict__[role.value].satisfaction
                for role in StakeholderRole
            }

        # --- Advance mission phase ---
        if self._mission_tracker is not None:
            approval = True
            if self._stakeholder_panel is not None:
                approval = self._stakeholder_panel.overall_approval

            mission_result = self._mission_tracker.step(
                rollout_pct=action.target_percentage,
                error_rate=observation.error_rate,
                stakeholder_approval=approval,
            )
            phase_advanced = mission_result["phase_advanced"]
            phase_progress_value = self._mission_tracker.phase_progress
            curr_ph = self._mission_tracker.current_phase
            phase_reward_weight = curr_ph.reward_weight if curr_ph else 1.0

        # --- Populate extended observation fields ---
        observation = self._populate_extended_obs(observation)
        self._update_analytics(observation)

        # --- Calculate reward ---
        use_extended = bool(stakeholder_sentiments or self._mission_tracker)

        if use_extended:
            # Pick base reward function based on difficulty
            base_fn = calculate_reward
            if self._state.difficulty == "easy":
                base_fn = calculate_reward_task1
            elif self._state.difficulty == "medium":
                base_fn = calculate_reward_task2
            elif self._state.difficulty == "hard":
                base_fn = calculate_reward_task3

            # Extract tool and communication metrics from history
            tools_used = sum(1 for a in self._state.action_history if getattr(a, "action_type", "") == "TOOL_CALL")
            comms_sent = sum(1 for a in self._state.action_history if getattr(a, "action_type", "") == "TOOL_CALL" and getattr(a, "tool_call", {}).get("tool_name", "") == "slack")

            reward = calculate_extended_reward(
                old_obs, observation, action,
                stakeholder_feedback_dict=observation.stakeholder_feedback_dict,
                phase_advanced=phase_advanced,
                phase_progress_value=phase_progress_value,
                phase_reward_weight=phase_reward_weight,
                tools_used=tools_used,
                communications_sent=comms_sent,
                action_history=self._state.action_history,
                base_reward_fn=base_fn,
                tool_reward_bonus=0.0 # Standard actions have no tool bonus
            )
        else:
            # Original reward path — unchanged
            reward = calculate_reward(old_obs, observation, action)
            if self._state.difficulty == "easy":
                reward = calculate_reward_task1(old_obs, observation, action)
            elif self._state.difficulty == "medium":
                reward = calculate_reward_task2(old_obs, observation, action)
            elif self._state.difficulty == "hard":
                reward = calculate_reward_task3(old_obs, observation, action)

       
        self._state.total_reward += reward

       
        done = self._check_done(observation, action)

        # Mission completion also triggers done
        if self._mission_tracker and self._mission_tracker.is_mission_complete:
            done = True

        # Task1 terminal shaping: penalize ending below minimum acceptable rollout.
        if done and self._state.difficulty == "easy" and observation.current_rollout_percentage < 23.0:
            reward -= 0.5

        self._state.done = done
        observation.done = done
        observation.reward = reward

        self._state.observation_history.append(observation)
        self.previous_observation = observation

        info = {
            "scenario_name": self._state.scenario_name,
            "difficulty": self._state.difficulty,
            "step_count": self._state.step_count,
            "total_reward": self._state.total_reward,
            "done_reason": self._get_done_reason(observation, action) if done else "",
        }

        # Add extended info
        if self._mission_tracker:
            info["mission"] = self._mission_tracker.to_info_dict()
            info["phase_advanced"] = phase_advanced

        if self._stakeholder_panel:
            info["stakeholder_approval"] = self._stakeholder_panel.overall_approval
            info["stakeholder_avg_sentiment"] = self._stakeholder_panel.average_sentiment

        return StepResponse(
            observation=observation,
            reward=reward,
            done=done,
            info=info,
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

    def _get_done_reason(self, observation, action) -> str:
        if self._state.step_count >= self._state.max_steps:
            return "max_steps_reached"
        if observation.error_rate > 0.25:
            return "catastrophic_error_rate"
        if action.target_percentage >= 100.0:
            return "full_rollout_requested"
        if self._mission_tracker and self._mission_tracker.is_mission_complete:
            return "mission_complete"
        return "task_or_env_condition"

    @property
    def extra_context(self) -> Dict[str, Any]:
        """
        Extended context for agents. Computes real-time pattern risk 
        without modifying core step logic.
        """
        if self._pattern_analyzer and self.previous_observation:
            self._extra_context_data["pattern_risk"] = self._pattern_analyzer.compute_risk(
                self.previous_observation.current_rollout_percentage,
                self.previous_observation.error_rate
            )
        return self._extra_context_data

    def set_customer_profile(self, profile: CustomerProfile):
        """Inject a customer profile and analyzer into the environment."""
        self._customer_profile = profile
        self._pattern_analyzer = PatternAnalyzer(profile)

    # --- Extended helpers ---------------------------------------------------

    def _populate_extended_obs(
        self, observation: FeatureFlagObservation
    ) -> FeatureFlagObservation:
        """Fill in stakeholder/mission/tool fields when features are enabled."""
        if self._stakeholder_panel is not None:
            # Old fields mapping for backward compatibility
            observation.stakeholder_devops_sentiment = (
                self._stakeholder_panel.devops.satisfaction * 2 - 1  # map [0,1]→[-1,1]
            )
            observation.stakeholder_product_sentiment = (
                self._stakeholder_panel.product.satisfaction * 2 - 1
            )
            observation.stakeholder_customer_sentiment = (
                self._stakeholder_panel.customer_success.satisfaction * 2 - 1
            )
            observation.stakeholder_overall_approval = (
                self._stakeholder_panel.overall_approval
            )

            # Generate new structured FeedbackVector
            fv = self._stakeholder_panel.get_feedback_vector(observation)
            observation.stakeholder_feedback_dict = {
                "devops_score": fv.devops_score,
                "product_score": fv.product_score,
                "customer_score": fv.customer_score,
                "devops_message": fv.devops_message,
                "product_message": fv.product_message,
                "customer_message": fv.customer_message,
                "consensus_score": fv.consensus_score,
                "conflict_level": fv.conflict_level,
                "majority_approval": fv.majority_approval,
                "all_concerns": fv.all_concerns,
            }
            
            # Extract belief tracking
            if self._stakeholder_panel.belief_tracker is not None:
                observation.stakeholder_belief_dict = self._stakeholder_panel.belief_tracker.summary()

        if self._mission_tracker is not None:
            info = self._mission_tracker.to_info_dict()
            observation.mission_name = info["mission_name"]
            observation.current_phase = info["current_phase"]
            observation.phase_index = info["phase_index"]
            observation.phase_progress = info["phase_progress"]
            observation.phases_completed = info["phases_completed"]
            observation.total_phases = info["total_phases"]
            
            current_p = self._mission_tracker.current_phase
            if current_p:
                observation.phase_objectives = current_p.objectives
                observation.phase_allowed_actions = current_p.allowed_actions

        if self._chaos_engine and self._chaos_engine.active_incident:
            observation.chaos_incident = self._chaos_engine.active_incident
            # Apply chaos effects to observation metrics (vandalize metrics slightly)
            if observation.chaos_incident["type"] == "latency_spike":
                observation.latency_p99_ms *= (1.0 + observation.chaos_incident["intensity"])
            elif observation.chaos_incident["type"] == "error_burst":
                observation.error_rate += observation.chaos_incident["intensity"] * 0.1

        if self._approval_workflow:
            observation.approval_status = self._approval_workflow.get_status()
            # If pending, simulate a human looking at it
            if observation.approval_status == "PENDING":
                conf = 1.0 - observation.error_rate * 10.0 # simple confidence metric
                self._approval_workflow.process_mock_approval(conf)

        # --- Anomaly Detection (Side-car) ---
        if self._anomaly_detector:
            # Update baseline with current observation
            metrics = {
                "error_rate": observation.error_rate,
                "latency_p99_ms": observation.latency_p99_ms,
                "revenue_impact": observation.revenue_impact,
                "system_health_score": observation.system_health_score
            }
            self._anomaly_detector.update_baselines(metrics)
            # Detect
            observation.extra_context["anomaly"] = self._anomaly_detector.detect(metrics)

        return observation

    def _update_analytics(self, observation: FeatureFlagObservation):
        """Update external analytics layer (non-agent, non-reward data)."""
        if self._benchmark_engine is not None:
            metrics = {
                "error_rate": observation.error_rate,
                "latency_p99_ms": observation.latency_p99_ms,
            }
            self.analytics["benchmark"] = self._benchmark_engine.analyze(metrics)

    def _handle_tool_call(self, action: FeatureFlagAction) -> StepResponse:
        """Handle TOOL_CALL action — dispatches to ToolManager, no rollout change."""
        old_obs = self.previous_observation

        # Count the step
        self._state.add_step(action, reward=0.0)

        # Dispatch tool call
        tool_result_data = None
        tool_reward_bonus = 0.0

        if self._tool_manager is not None and action.tool_call is not None:
            # Propagate env state to mock tools
            self._tool_manager.update_env_state({
                "error_rate": old_obs.error_rate,
                "latency_p99_ms": old_obs.latency_p99_ms,
                "rollout_percentage": old_obs.current_rollout_percentage,
                "system_health_score": old_obs.system_health_score,
                "active_users": old_obs.active_users,
            })

            request = ToolCallRequest(
                tool_name=action.tool_call.get("tool_name", ""),
                action_name=action.tool_call.get("action_name", ""),
                params=action.tool_call.get("params", {}),
            )
            result = self._tool_manager.execute(request)
            tool_result_data = self._tool_manager.get_last_result_dict()

            # Small reward for successful tool use
            if result.success:
                tool_reward_bonus = 0.05
            else:
                tool_reward_bonus = -0.02
        else:
            tool_reward_bonus = -0.05  # penalty for invalid tool call
            tool_result_data = {
                "tool": action.tool_call.get("tool_name", "unknown") if action.tool_call else "unknown",
                "action": action.tool_call.get("action_name", "unknown") if action.tool_call else "unknown",
                "success": False,
                "error": "Tool Integration Layer is disabled or ToolManager is missing.",
                "latency_ms": 0.0
            }

        # Observation stays unchanged (no new simulator step — rollout frozen)
        observation = FeatureFlagObservation(
            current_rollout_percentage=old_obs.current_rollout_percentage,
            error_rate=old_obs.error_rate,
            latency_p99_ms=old_obs.latency_p99_ms,
            user_adoption_rate=old_obs.user_adoption_rate,
            revenue_impact=old_obs.revenue_impact,
            system_health_score=old_obs.system_health_score,
            active_users=old_obs.active_users,
            feature_name=old_obs.feature_name,
            time_step=self._state.step_count,
            reward=0.0, # Placeholder
            done=False,
        )

        # Populate extended fields including tool results
        observation = self._populate_extended_obs(observation)
        if tool_result_data:
            observation.last_tool_result = tool_result_data
        if self._tool_manager:
            observation.tool_memory_summary = self._tool_manager.memory.summary()

        # --- Calculate extended reward for tool call ---
        phase_progress_value = 0.0
        phase_reward_weight = 1.0
        if self._mission_tracker:
            phase_progress_value = self._mission_tracker.phase_progress
            if self._mission_tracker.current_phase:
                phase_reward_weight = self._mission_tracker.current_phase.reward_weight

        # Extract tool and communication metrics from history
        tools_used = sum(1 for a in self._state.action_history if a.action_type == "TOOL_CALL")
        comms_sent = sum(1 for a in self._state.action_history if a.action_type == "TOOL_CALL" and a.tool_call and a.tool_call.get("tool_name", "") == "slack")

        reward = calculate_extended_reward(
            old_obs, observation, action,
            stakeholder_feedback_dict=observation.stakeholder_feedback_dict,
            phase_advanced=False,
            phase_progress_value=phase_progress_value,
            phase_reward_weight=phase_reward_weight,
            tools_used=tools_used,
            communications_sent=comms_sent,
            action_history=self._state.action_history,
            base_reward_fn=calculate_reward, # Tool calls use standard base
            tool_reward_bonus=tool_reward_bonus
        )

        observation.reward = reward
        self._state.total_reward += reward

        done = self._check_done(observation, action)
        self._state.done = done
        observation.done = done

        self._state.observation_history.append(observation)
        self.previous_observation = observation

        info = {
            "scenario_name": self._state.scenario_name,
            "difficulty": self._state.difficulty,
            "step_count": self._state.step_count,
            "total_reward": self._state.total_reward,
            "done_reason": self._get_done_reason(observation, action) if done else "",
            "tool_call_result": tool_result_data,
        }

        return StepResponse(
            observation=observation,
            reward=reward,
            done=done,
            info=info,
        )

    @property
    def observation_space(self):
        """
        Dynamically generates the canonical continuous RL `Box` bounding ranges matching
        the 19-dimensional vector extraction in FeatureFlagObservation.to_numpy_array().
        """
        import numpy as np
        
        lows = np.array([0.0, 0.0, 0.0, 0.0, 0.0, -1.0, -1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        highs = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float32)
        
        try:
            from gymnasium.spaces import Box
            return Box(low=lows, high=highs, dtype=np.float32)
        except ImportError:
            try:
                from gym.spaces import Box
                return Box(low=lows, high=highs, dtype=np.float32)
            except ImportError:
                # Provides a pseudo environment space shape
                class PseudoBox:
                    def __init__(self, low, high, shape, dtype):
                        self.low = low
                        self.high = high
                        self.shape = shape
                        self.dtype = dtype
                return PseudoBox(lows, highs, (19,), np.float32)


def make_environment(
    scenario_config: Optional[Dict[str, Any]] = None,
    stakeholders_enabled: bool = False,
    mission_config: Optional[str] = None,
    tools_enabled: bool = False,
    tool_manager: Optional[ToolManager] = None,
    chaos_enabled: bool = False,
    hitl_enabled: bool = False,
    benchmarking_config: Optional[Dict[str, str]] = None,
):
    """Canonical factory for FeatureFlagEnvironment."""
    return FeatureFlagEnvironment(
        scenario_config,
        stakeholders_enabled=stakeholders_enabled,
        mission_config=mission_config,
        tools_enabled=tools_enabled,
        tool_manager=tool_manager,
        chaos_enabled=chaos_enabled,
        hitl_enabled=hitl_enabled,
        benchmarking_config=benchmarking_config,
    )


# TASK-SPECIFIC FACTORY HELPERS (For direct task imports)

def make_task1_environment():
    """Factory for Task 1: Safe Rollout (easy difficulty)."""
    from feature_flag_env.tasks.task1_safe_rollout import make_task1_environment as _make_task1_environment

    return _make_task1_environment()


def make_task2_environment():
    """Factory for Task 2: Risk-Aware Scaling (medium difficulty)."""
    from feature_flag_env.tasks.task2_risk_aware import make_task2_environment as _make_task2_environment

    return _make_task2_environment()


def make_task3_environment():
    """Factory for Task 3: Multi-Objective Optimization (hard difficulty)."""
    from feature_flag_env.tasks.task3_multi_objective import make_task3_environment as _make_task3_environment

    return _make_task3_environment()
