"""
feature_flag_env/models.py

Defines core data structures for Agent ↔ Environment communication.
This is the "language" of the system.
"""

from pydantic import BaseModel, Field
from typing import Literal, List, Optional
from datetime import datetime, timezone  
import uuid



class FeatureFlagAction(BaseModel):
    """
    Represents a decision made by the Agent.
    """

    action_type: Literal[
        "INCREASE_ROLLOUT",
        "DECREASE_ROLLOUT",
        "MAINTAIN",
        "HALT_ROLLOUT",
        "FULL_ROLLOUT",
        "ROLLBACK"
    ]

    target_percentage: float = Field(
        ge=0.0,
        le=100.0,
        description="Target rollout percentage"
    )

    reason: str = Field(
        default="",
        max_length=500,
        description="Agent reasoning"
    )

   
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __str__(self) -> str:
        return f"{self.action_type} → {self.target_percentage}%"


class FeatureFlagObservation(BaseModel):
    """
    Represents the current system state (input to agent).
    """

    current_rollout_percentage: float = Field(ge=0.0, le=100.0)
    error_rate: float = Field(ge=0.0, le=1.0)
    latency_p99_ms: float = Field(ge=0.0)
    user_adoption_rate: float = Field(ge=0.0, le=1.0)
    revenue_impact: float
    system_health_score: float = Field(ge=0.0, le=1.0)
    active_users: int = Field(ge=0)

    feature_name: str
    time_step: int = Field(ge=0)

   
    reward: Optional[float] = Field(default=None, description="Reward from previous step")
    done: Optional[bool] = Field(default=False, description="Episode complete")

    def to_prompt_string(self) -> str:
        """
        Converts observation into LLM-friendly text.
        """
        reward_str = f"Reward: {self.reward:.2f}" if self.reward is not None else "Reward: N/A"
        done_str = "DONE" if self.done else "CONTINUE"
        
        return f"""
SYSTEM STATE:

Feature: {self.feature_name}
Step: {self.time_step}
Status: {done_str}
{reward_str}

Metrics:
- Rollout: {self.current_rollout_percentage:.1f}%
- Error Rate: {self.error_rate:.4f}
- Latency (p99): {self.latency_p99_ms:.1f} ms
- Adoption: {self.user_adoption_rate:.4f}
- Revenue: {self.revenue_impact:.2f}
- Health Score: {self.system_health_score:.2f}
- Active Users: {self.active_users}

GOAL:
Maximize rollout and revenue while keeping:
- Error rate < 0.05
- Latency < 200 ms
"""

    def __repr__(self):
        return (
            f"<Obs rollout={self.current_rollout_percentage}% "
            f"error={self.error_rate:.3f} "
            f"latency={self.latency_p99_ms:.1f}>"
        )



class FeatureFlagState(BaseModel):
    """
    Tracks episode-level metadata.
    """

    episode_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_count: int = Field(default=0, ge=0)
    max_steps: int = Field(default=50, ge=1)
    total_reward: float = Field(default=0.0)

    rollout_history: List[float] = Field(default_factory=list)
   
    action_history: List[str] = Field(default_factory=list)

    done: bool = Field(default=False)

    scenario_name: Optional[str] = None
    difficulty: Optional[str] = "medium"

    def add_step(self, action: FeatureFlagAction, reward: float):
        """
        Record step progress
        """
        self.step_count += 1
        self.total_reward += reward
        self.rollout_history.append(action.target_percentage)
        self.action_history.append(action.action_type)  

    def is_episode_complete(self) -> bool:
        return self.done or self.step_count >= self.max_steps



class StepResponse(BaseModel):
    """
    Standard RL step output
    """
    observation: FeatureFlagObservation
    reward: float
    done: bool
    info: dict = Field(default_factory=dict)


class ResetResponse(BaseModel):
    """
    Standard RL reset output
    """
    observation: FeatureFlagObservation
    info: dict = Field(default_factory=dict)