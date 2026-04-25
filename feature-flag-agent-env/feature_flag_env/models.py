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
    phase_objectives: Optional[List[str]] = Field(
        default=None, description="Current phase qualitative objectives"
    )
    phase_allowed_actions: Optional[List[str]] = Field(
        default=None, description="Allowed actions in the current phase"
    )

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

        if self.mission_name is not None:
            po = "- " + "\n- ".join(self.phase_objectives or []) if self.phase_objectives is not None else "None"
            pa = ", ".join(self.phase_allowed_actions or []) if self.phase_allowed_actions is not None else "All"
            _idx = self.phase_index if self.phase_index is not None else 0
            _total = self.total_phases if self.total_phases is not None else 1
            _progress = self.phase_progress if self.phase_progress is not None else 0.0
            parts.append(f"""
MISSION & PHASE:
- Mission: {self.mission_name} (Phase {_idx + 1}/{_total}: {self.current_phase})
- Phase Progress: {_progress * 100:.0f}%
- allowed_actions: [{pa}]
- Objectives:
{po}
""")

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
            _idx = self.phase_index if self.phase_index is not None else 0
            _total = self.total_phases if self.total_phases is not None else 1
            _progress = self.phase_progress if self.phase_progress is not None else 0.0
            parts.append(f"""
MISSION PROGRESS:
- Mission: {self.mission_name}
- Phase: {self.current_phase} ({_idx}/{_total})
- Phase Progress: {_progress:.0%}
- Phases Completed: {self.phases_completed or 0}/{_total}
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

    def to_numpy_array(self) -> Any:
        import numpy as np

        def _clip(val: float, min_val: float, max_val: float) -> float:
            return max(min_val, min(val, max_val))

        vector = np.zeros(17, dtype=np.float32)

        # Base Metrics (0-4)
        vector[0] = self.current_rollout_percentage / 100.0
        vector[1] = _clip(self.error_rate, 0.0, 1.0)
        vector[2] = _clip(self.latency_p99_ms / 500.0, 0.0, 1.0)
        vector[3] = _clip(self.user_adoption_rate, 0.0, 1.0)
        vector[4] = _clip(self.system_health_score, 0.0, 1.0)

        # Stakeholders (5-10)
        fd = self.stakeholder_feedback_dict or {}
        vector[5] = _clip(fd.get("devops_score", self.stakeholder_devops_sentiment or 0.0), -1.0, 1.0)
        vector[6] = _clip(fd.get("product_score", self.stakeholder_product_sentiment or 0.0), -1.0, 1.0)
        vector[7] = _clip(fd.get("customer_score", self.stakeholder_customer_sentiment or 0.0), -1.0, 1.0)
        vector[8] = _clip(fd.get("consensus_score", 0.0), -1.0, 1.0)
        vector[9] = _clip(fd.get("conflict_level", 0.0), 0.0, 1.0)
        
        maj = fd.get("majority_approval", self.stakeholder_overall_approval)
        vector[10] = 1.0 if maj else 0.0

        # Mission (11-12)
        total_p = max(1, self.total_phases or 1)
        vector[11] = _clip((self.phase_index or 0) / float(total_p), 0.0, 1.0)
        vector[12] = _clip(self.phase_progress or 0.0, 0.0, 1.0)

        # Tools (13-16)
        vector[13] = _clip((self.tools_connected or 0) / 10.0, 0.0, 1.0)
        vector[14] = _clip((self.tools_alerts_active or 0) / 5.0, 0.0, 1.0)
        
        tr = self.last_tool_result or {}
        vector[15] = 1.0 if tr.get("success") else 0.0
        vector[16] = _clip(tr.get("latency_ms", 0) / 2000.0, 0.0, 1.0)

        return vector

class FeatureFlagState(BaseModel):
    """
    Tracks episode-level metadata.
    """

    episode_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_count: int = Field(default=0, ge=0)
    max_steps: int = Field(default=50, ge=1)
    total_reward: float = Field(default=0.0)

    rollout_history: List[float] = Field(default_factory=list)
   
    action_history: List[FeatureFlagAction] = Field(default_factory=list)

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
        self.action_history.append(action)  

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