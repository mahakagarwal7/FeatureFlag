"""
feature_flag_env/models.py

Defines core data structures for Agent ↔ Environment communication.
This is the "language" of the system.
"""

from pydantic import BaseModel, Field
from typing import Dict, Literal, List, Optional, Any
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
        "ROLLBACK",
        "TOOL_CALL"
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

    # --- Extended: Tool call request (optional) ---
    tool_call: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Tool call request: {tool_name, action_name, params}"
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

    # --- Extended: Stakeholder feedback (Feature 1) ---
    stakeholder_devops_sentiment: Optional[float] = Field(
        default=None, ge=-1.0, le=1.0, description="DevOps sentiment"
    )
    stakeholder_product_sentiment: Optional[float] = Field(
        default=None, ge=-1.0, le=1.0, description="Product sentiment"
    )
    stakeholder_customer_sentiment: Optional[float] = Field(
        default=None, ge=-1.0, le=1.0, description="Customer Success sentiment"
    )
    stakeholder_overall_approval: Optional[bool] = Field(
        default=None, description="Majority stakeholder approval"
    )
    stakeholder_feedback_dict: Optional[Dict[str, Any]] = Field(
        default=None, description="Detailed FeedbackVector summary"
    )
    stakeholder_belief_dict: Optional[Dict[str, Any]] = Field(
        default=None, description="BeliefTracker trends summary"
    )

    # --- Extended: Mission progress (Feature 2) ---
    mission_name: Optional[str] = Field(default=None)
    current_phase: Optional[str] = Field(default=None)
    phase_index: Optional[int] = Field(default=None, ge=0)
    phase_progress: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Progress within phase"
    )
    phases_completed: Optional[int] = Field(default=None, ge=0)
    total_phases: Optional[int] = Field(default=None, ge=0)

    # --- Extended: Tool status summary ---
    tools_connected: Optional[int] = Field(default=None, ge=0)
    tools_alerts_active: Optional[int] = Field(default=None, ge=0)
    last_tool_result: Optional[Dict[str, Any]] = Field(
        default=None, description="Most recent tool call result"
    )
    tool_memory_summary: Optional[Dict[str, Any]] = Field(
        default=None, description="Rolling summary of recent tool calls"
    )

    def to_prompt_string(self) -> str:
        """
        Converts observation into LLM-friendly text.
        """
        reward_str = f"Reward: {self.reward:.2f}" if self.reward is not None else "Reward: N/A"
        done_str = "DONE" if self.done else "CONTINUE"
        
        base_str = f"""
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
        # --- Extended sections (only rendered when populated) ---
        parts = [base_str]

        if self.stakeholder_feedback_dict is not None:
            fd = self.stakeholder_feedback_dict
            parts.append(f"""
STAKEHOLDER FEEDBACK VECTOR:
- DevOps Sentiment:  {fd.get('devops_score', 0.0):+.2f} — {fd.get('devops_message', '')}
- Product Sentiment: {fd.get('product_score', 0.0):+.2f} — {fd.get('product_message', '')}
- Customer Success:  {fd.get('customer_score', 0.0):+.2f} — {fd.get('customer_message', '')}
- Consensus Score:   {fd.get('consensus_score', 0.0):+.2f}  |  Conflict Level: {fd.get('conflict_level', 0.0):.2f}
- Majority Approval: {'YES' if fd.get('majority_approval') else 'NO'}
- Priority Concerns: {'; '.join(fd.get('all_concerns', [])) if fd.get('all_concerns') else 'None'}
""")
        elif self.stakeholder_devops_sentiment is not None:
            # Fallback for older tests using the raw sentiment fields
            _do = f"{self.stakeholder_devops_sentiment:+.2f}"
            _pr = f"{self.stakeholder_product_sentiment:+.2f}" if self.stakeholder_product_sentiment is not None else "N/A"
            _cs = f"{self.stakeholder_customer_sentiment:+.2f}" if self.stakeholder_customer_sentiment is not None else "N/A"
            _ap = "YES" if self.stakeholder_overall_approval else "NO"
            parts.append(f"""
STAKEHOLDER FEEDBACK:
- DevOps Sentiment: {_do}
- Product Sentiment: {_pr}
- Customer Success: {_cs}
- Overall Approval: {_ap}
""")

        if self.stakeholder_belief_dict is not None:
            bd = self.stakeholder_belief_dict
            trends = bd.get('satisfaction_trends', {})
            _dt = trends.get('devops', 'stable')
            _pt = trends.get('product', 'stable')
            _ct = trends.get('customer_success', 'stable')
            parts.append(f"""
BELIEF & TRENDS (Last {bd.get('steps_tracked', 0)} steps):
- Satisfaction Trends: DevOps ({_dt}), Product ({_pt}), Customer ({_ct})
- Conflict Trend: {bd.get('conflict_trend', 'stable')} (Latest: {bd.get('latest_conflict', 0.0):.2f})
""")

        if self.mission_name is not None:
            parts.append(f"""
MISSION PROGRESS:
- Mission: {self.mission_name}
- Phase: {self.current_phase} ({self.phase_index}/{self.total_phases})
- Phase Progress: {self.phase_progress:.0%}
- Phases Completed: {self.phases_completed}/{self.total_phases}
""")

        if self.tools_connected is not None:
            parts.append(f"""
TOOL STATUS:
- Connected Tools: {self.tools_connected}
- Active Alerts: {self.tools_alerts_active or 0}
""")

        if self.last_tool_result is not None:
            tr = self.last_tool_result
            _status = "SUCCESS" if tr.get("success") else "FAILED"
            _err = f" ({tr.get('error')})" if tr.get("error") else ""
            parts.append(f"""
LAST TOOL RESULT:
- Tool: {tr.get('tool', 'N/A')}.{tr.get('action', 'N/A')}
- Status: {_status}{_err}
- Latency: {tr.get('latency_ms', 0):.0f}ms
""")

        return "\n".join(parts)

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