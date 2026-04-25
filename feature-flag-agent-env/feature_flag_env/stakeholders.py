"""
feature_flag_env/stakeholders.py

Multi-stakeholder feedback system for enterprise deployment simulation.

Three simulated personas provide sentiment-based feedback each step:
- DevOps: cares about errors, latency, system health
- Product: cares about rollout progress, adoption rate
- Customer Success: cares about user satisfaction (adoption × health)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from feature_flag_env.models import FeatureFlagObservation


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class StakeholderRole(str, Enum):
    DEVOPS = "devops"
    PRODUCT = "product"
    CUSTOMER_SUCCESS = "customer_success"


@dataclass
class StakeholderFeedback:
    """Single-step feedback from one stakeholder."""

    role: StakeholderRole
    sentiment: float          # -1.0 (very unhappy) to +1.0 (very happy)
    approval: bool            # would this stakeholder approve the current state?
    message: str              # human-readable explanation
    priority_concerns: List[str] = field(default_factory=list)


@dataclass
class StakeholderPreferences:
    """
    Configurable preference weights for a stakeholder.
    Weights determine how much each metric dimension affects sentiment.
    All weights should sum to ~1.0 for normalized scoring.
    """
    stability_weight: float = 0.0   # error rate, latency sensitivity
    velocity_weight: float = 0.0    # rollout progress sensitivity
    experience_weight: float = 0.0  # user satisfaction sensitivity
    revenue_weight: float = 0.0     # revenue impact sensitivity

    @staticmethod
    def devops() -> StakeholderPreferences:
        return StakeholderPreferences(
            stability_weight=0.6, velocity_weight=0.05,
            experience_weight=0.15, revenue_weight=0.2
        )

    @staticmethod
    def product() -> StakeholderPreferences:
        return StakeholderPreferences(
            stability_weight=0.1, velocity_weight=0.5,
            experience_weight=0.15, revenue_weight=0.25
        )

    @staticmethod
    def customer_success() -> StakeholderPreferences:
        return StakeholderPreferences(
            stability_weight=0.2, velocity_weight=0.05,
            experience_weight=0.55, revenue_weight=0.2
        )


@dataclass
class FeedbackVector:
    """
    Structured composite feedback from all stakeholders.

    Contains individual scores, messages, an aggregate consensus
    signal, and a conflict_level indicating stakeholder disagreement.
    """

    devops_score: float           # [-1, +1]
    product_score: float
    customer_score: float
    devops_message: str
    product_message: str
    customer_message: str
    devops_concerns: List[str]
    product_concerns: List[str]
    customer_concerns: List[str]
    consensus_score: float        # weighted average of all scores
    conflict_level: float         # 0.0 (agreement) → 1.0 (total conflict)
    majority_approval: bool       # ≥ 2 of 3 approve
    all_concerns: List[str] = field(default_factory=list)

    @property
    def has_conflict(self) -> bool:
        """True when stakeholders significantly disagree (conflict > 0.4)."""
        return self.conflict_level > 0.4

    @property
    def scores_array(self) -> List[float]:
        return [self.devops_score, self.product_score, self.customer_score]

    def to_prompt_section(self) -> str:
        """Pretty format for agent prompt injection."""
        lines = [
            "STAKEHOLDER FEEDBACK VECTOR:",
            f"  DevOps:    {self.devops_score:+.2f} — {self.devops_message}",
            f"  Product:   {self.product_score:+.2f} — {self.product_message}",
            f"  Customer:  {self.customer_score:+.2f} — {self.customer_message}",
            f"  Consensus: {self.consensus_score:+.2f}  Conflict: {self.conflict_level:.2f}",
            f"  Approval:  {'YES' if self.majority_approval else 'NO'}",
        ]
        if self.all_concerns:
            lines.append(f"  Concerns:  {'; '.join(self.all_concerns)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Base stakeholder
# ---------------------------------------------------------------------------

class BaseStakeholder:
    """
    Abstract stakeholder that tracks a rolling satisfaction score (EMA).
    Subclasses implement ``_evaluate`` to produce raw feedback.
    """

    EMA_ALPHA = 0.3  # smoothing factor for exponential moving average

    def __init__(self, role: StakeholderRole,
                 preferences: Optional[StakeholderPreferences] = None):
        self.role = role
        self.preferences = preferences or StakeholderPreferences()
        self.satisfaction: float = 0.5  # neutral starting point
        self._history: List[StakeholderFeedback] = []

    # -- public API ----------------------------------------------------------

    def get_feedback(self, observation: FeatureFlagObservation) -> StakeholderFeedback:
        """Evaluate current observation, update satisfaction, return feedback."""
        fb = self._evaluate(observation)
        # Update EMA satisfaction
        self.satisfaction = (
            self.EMA_ALPHA * ((fb.sentiment + 1.0) / 2.0)  # map [-1,1] → [0,1]
            + (1 - self.EMA_ALPHA) * self.satisfaction
        )
        self._history.append(fb)
        return fb

    def reset(self) -> None:
        """Reset state at episode start."""
        self.satisfaction = 0.5
        self._history.clear()

    @property
    def history(self) -> List[StakeholderFeedback]:
        return list(self._history)

    # -- to be overridden ----------------------------------------------------

    def _evaluate(self, obs: FeatureFlagObservation) -> StakeholderFeedback:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Concrete stakeholders
# ---------------------------------------------------------------------------

class DevOpsStakeholder(BaseStakeholder):
    """
    Cares about operational stability:
    - error_rate < 0.05
    - latency_p99_ms < 200
    - system_health_score > 0.7
    """

    # Thresholds
    ERROR_OK = 0.05
    ERROR_CRITICAL = 0.15
    LATENCY_OK = 200.0
    LATENCY_CRITICAL = 400.0
    HEALTH_OK = 0.7

    def __init__(self, preferences: Optional[StakeholderPreferences] = None):
        super().__init__(StakeholderRole.DEVOPS,
                         preferences or StakeholderPreferences.devops())

    def _evaluate(self, obs: FeatureFlagObservation) -> StakeholderFeedback:
        concerns: List[str] = []
        sentiment = 0.0

        # --- Error rate ---
        if obs.error_rate < self.ERROR_OK:
            sentiment += 0.4
        elif obs.error_rate < self.ERROR_CRITICAL:
            sentiment -= 0.3
            concerns.append(f"error rate elevated ({obs.error_rate:.2%})")
        else:
            sentiment -= 0.6
            concerns.append(f"error rate CRITICAL ({obs.error_rate:.2%})")

        # --- Latency ---
        if obs.latency_p99_ms < self.LATENCY_OK:
            sentiment += 0.3
        elif obs.latency_p99_ms < self.LATENCY_CRITICAL:
            sentiment -= 0.2
            concerns.append(f"latency elevated ({obs.latency_p99_ms:.0f}ms)")
        else:
            sentiment -= 0.5
            concerns.append(f"latency CRITICAL ({obs.latency_p99_ms:.0f}ms)")

        # --- Health score ---
        if obs.system_health_score >= self.HEALTH_OK:
            sentiment += 0.3
        else:
            sentiment -= 0.3
            concerns.append(f"system health low ({obs.system_health_score:.2f})")

        sentiment = max(-1.0, min(1.0, sentiment))
        approval = len(concerns) == 0

        if approval:
            message = "Systems nominal. Clear to proceed."
        elif sentiment > -0.3:
            message = "Minor concerns — monitor closely."
        else:
            message = "HOLD deployment — operational issues detected."

        return StakeholderFeedback(
            role=self.role,
            sentiment=sentiment,
            approval=approval,
            message=message,
            priority_concerns=concerns,
        )


class ProductStakeholder(BaseStakeholder):
    """
    Cares about feature velocity:
    - rollout progress toward 100 %
    - user adoption rate
    """

    ADOPTION_GOOD = 0.3
    ROLLOUT_STALL_THRESHOLD = 2.0  # % change considered "stalled"

    def __init__(self, preferences: Optional[StakeholderPreferences] = None):
        super().__init__(StakeholderRole.PRODUCT,
                         preferences or StakeholderPreferences.product())
        self._prev_rollout: Optional[float] = None

    def reset(self) -> None:
        super().reset()
        self._prev_rollout = None

    def _evaluate(self, obs: FeatureFlagObservation) -> StakeholderFeedback:
        concerns: List[str] = []
        sentiment = 0.0

        # --- Rollout progress ---
        rollout_delta = 0.0
        if self._prev_rollout is not None:
            rollout_delta = obs.current_rollout_percentage - self._prev_rollout
        self._prev_rollout = obs.current_rollout_percentage

        if rollout_delta > self.ROLLOUT_STALL_THRESHOLD:
            sentiment += 0.5  # good progress
        elif rollout_delta >= 0:
            sentiment += 0.1  # holding or tiny progress
            if obs.current_rollout_percentage < 50:
                concerns.append("rollout velocity is low")
        else:
            sentiment -= 0.3
            concerns.append("rollout is decreasing")

        # --- Adoption ---
        if obs.user_adoption_rate >= self.ADOPTION_GOOD:
            sentiment += 0.4
        else:
            sentiment -= 0.1
            concerns.append(f"adoption low ({obs.user_adoption_rate:.1%})")

        # --- Absolute rollout level bonus ---
        sentiment += (obs.current_rollout_percentage / 100.0) * 0.2

        sentiment = max(-1.0, min(1.0, sentiment))
        approval = rollout_delta >= 0 and obs.current_rollout_percentage > 0

        if approval and not concerns:
            message = "Feature momentum looks great — keep shipping!"
        elif concerns:
            message = "Need to pick up the pace on rollout."
        else:
            message = "Watching rollout progress."

        return StakeholderFeedback(
            role=self.role,
            sentiment=sentiment,
            approval=approval,
            message=message,
            priority_concerns=concerns,
        )


class CustomerSuccessStakeholder(BaseStakeholder):
    """
    Cares about end-user experience:
    - user satisfaction proxy = adoption × health
    - high errors + many active users = complaints
    """

    SATISFACTION_PROXY_GOOD = 0.5  # adoption * health threshold

    def __init__(self, preferences: Optional[StakeholderPreferences] = None):
        super().__init__(StakeholderRole.CUSTOMER_SUCCESS,
                         preferences or StakeholderPreferences.customer_success())

    def _evaluate(self, obs: FeatureFlagObservation) -> StakeholderFeedback:
        concerns: List[str] = []
        sentiment = 0.0

        user_satisfaction = obs.user_adoption_rate * obs.system_health_score

        # --- User satisfaction proxy ---
        if user_satisfaction >= self.SATISFACTION_PROXY_GOOD:
            sentiment += 0.5
        elif user_satisfaction >= 0.2:
            sentiment += 0.1
        else:
            sentiment -= 0.2
            concerns.append("user satisfaction is low")

        # --- Complaint risk: high errors with many users ---
        complaint_risk = obs.error_rate * (obs.active_users / max(1, 10000))
        if complaint_risk > 0.05:
            sentiment -= 0.5
            concerns.append(f"high complaint risk ({complaint_risk:.2f})")
        elif complaint_risk > 0.02:
            sentiment -= 0.2
            concerns.append("moderate complaint risk")

        # --- Revenue health ---
        if obs.revenue_impact > 0:
            sentiment += 0.2

        sentiment = max(-1.0, min(1.0, sentiment))
        approval = complaint_risk < 0.05 and user_satisfaction >= 0.1

        if approval and not concerns:
            message = "Customers are happy — no complaints."
        elif concerns:
            message = "Seeing user experience concerns."
        else:
            message = "Monitoring customer feedback."

        return StakeholderFeedback(
            role=self.role,
            sentiment=sentiment,
            approval=approval,
            message=message,
            priority_concerns=concerns,
        )


# ---------------------------------------------------------------------------
# Convenience: panel of all three stakeholders
# ---------------------------------------------------------------------------

@dataclass
class StakeholderPanel:
    """Manages all stakeholders as a group."""

    devops: DevOpsStakeholder = field(default_factory=DevOpsStakeholder)
    product: ProductStakeholder = field(default_factory=ProductStakeholder)
    customer_success: CustomerSuccessStakeholder = field(
        default_factory=CustomerSuccessStakeholder
    )
    _belief_tracker: Optional[BeliefTracker] = field(
        default=None, init=False, repr=False
    )

    def reset(self) -> None:
        self.devops.reset()
        self.product.reset()
        self.customer_success.reset()
        self._belief_tracker = BeliefTracker()

    def get_all_feedback(
        self, observation: FeatureFlagObservation
    ) -> Dict[StakeholderRole, StakeholderFeedback]:
        fbs = {
            StakeholderRole.DEVOPS: self.devops.get_feedback(observation),
            StakeholderRole.PRODUCT: self.product.get_feedback(observation),
            StakeholderRole.CUSTOMER_SUCCESS: self.customer_success.get_feedback(
                observation
            ),
        }
        # update belief tracker
        if self._belief_tracker is not None:
            self._belief_tracker.update(fbs)
        return fbs

    def get_feedback_vector(
        self, observation: FeatureFlagObservation
    ) -> FeedbackVector:
        """
        Get structured FeedbackVector from all stakeholders.
        Also updates belief tracker internally.
        """
        fbs = self.get_all_feedback(observation)
        d = fbs[StakeholderRole.DEVOPS]
        p = fbs[StakeholderRole.PRODUCT]
        c = fbs[StakeholderRole.CUSTOMER_SUCCESS]

        scores = [d.sentiment, p.sentiment, c.sentiment]
        mean = sum(scores) / 3.0
        variance = sum((s - mean) ** 2 for s in scores) / 3.0
        conflict = min(1.0, math.sqrt(variance))  # 0 = agreement, 1 = max conflict

        all_concerns = d.priority_concerns + p.priority_concerns + c.priority_concerns

        return FeedbackVector(
            devops_score=d.sentiment,
            product_score=p.sentiment,
            customer_score=c.sentiment,
            devops_message=d.message,
            product_message=p.message,
            customer_message=c.message,
            devops_concerns=d.priority_concerns,
            product_concerns=p.priority_concerns,
            customer_concerns=c.priority_concerns,
            consensus_score=mean,
            conflict_level=conflict,
            majority_approval=self.overall_approval,
            all_concerns=all_concerns,
        )

    @property
    def overall_approval(self) -> bool:
        """Majority approval (≥ 2 of 3)."""
        approvals = [
            self.devops.satisfaction >= 0.5,
            self.product.satisfaction >= 0.5,
            self.customer_success.satisfaction >= 0.5,
        ]
        return sum(approvals) >= 2

    @property
    def average_sentiment(self) -> float:
        """Average of latest feedback sentiments (for reward signal)."""
        sats = [
            self.devops.satisfaction,
            self.product.satisfaction,
            self.customer_success.satisfaction,
        ]
        return sum(sats) / len(sats)

    @property
    def belief_tracker(self) -> Optional[BeliefTracker]:
        return self._belief_tracker


# ---------------------------------------------------------------------------
# Belief Tracker — agent-side satisfaction modeling
# ---------------------------------------------------------------------------

class BeliefTracker:
    """
    Tracks per-stakeholder satisfaction trends over time.

    Features:
      - Rolling satisfaction history per role
      - Trend detection (improving / declining / stable)
      - Conflict identification between stakeholders
      - Summary dict for agent prompt injection
    """

    TREND_WINDOW = 5  # steps to look back for trend detection
    TREND_THRESHOLD = 0.1  # min change to count as improving/declining

    def __init__(self):
        self._satisfaction_history: Dict[StakeholderRole, List[float]] = {
            StakeholderRole.DEVOPS: [],
            StakeholderRole.PRODUCT: [],
            StakeholderRole.CUSTOMER_SUCCESS: [],
        }
        self._conflict_history: List[float] = []

    def update(self, feedbacks: Dict[StakeholderRole, StakeholderFeedback]) -> None:
        """Record feedback sentiments for belief tracking."""
        scores = []
        for role, fb in feedbacks.items():
            self._satisfaction_history[role].append(fb.sentiment)
            scores.append(fb.sentiment)

        if scores:
            mean = sum(scores) / len(scores)
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            self._conflict_history.append(min(1.0, math.sqrt(variance)))

    def get_trend(self, role: StakeholderRole) -> str:
        """Detect trend: 'improving', 'declining', or 'stable'."""
        history = self._satisfaction_history.get(role, [])
        if len(history) < self.TREND_WINDOW:
            return "stable"

        recent = history[-self.TREND_WINDOW:]
        first_half = sum(recent[:len(recent)//2]) / max(1, len(recent)//2)
        second_half = sum(recent[len(recent)//2:]) / max(1, len(recent) - len(recent)//2)
        delta = second_half - first_half

        if delta > self.TREND_THRESHOLD:
            return "improving"
        elif delta < -self.TREND_THRESHOLD:
            return "declining"
        return "stable"

    def get_all_trends(self) -> Dict[str, str]:
        return {
            role.value: self.get_trend(role)
            for role in list(StakeholderRole)
        }

    def get_conflict_trend(self) -> str:
        """Is conflict increasing, decreasing, or stable?"""
        if len(self._conflict_history) < self.TREND_WINDOW:
            return "stable"
        recent = self._conflict_history[-self.TREND_WINDOW:]
        first = sum(recent[:2]) / 2
        last = sum(recent[-2:]) / 2
        delta = last - first
        if delta > 0.1:
            return "increasing"
        elif delta < -0.1:
            return "decreasing"
        return "stable"

    def summary(self) -> Dict:
        """Compact summary for agent observation injection."""
        trends = self.get_all_trends()
        return {
            "satisfaction_trends": trends,
            "conflict_trend": self.get_conflict_trend(),
            "steps_tracked": len(self._conflict_history),
            "latest_conflict": (
                self._conflict_history[-1] if self._conflict_history else 0.0
            ),
        }


# ---------------------------------------------------------------------------
# Conflict Scenarios — predefined situations where stakeholders disagree
# ---------------------------------------------------------------------------

class ConflictScenarios:
    """
    Generates observation sequences simulating stakeholder conflicts.

    Scenarios:
      speed_vs_stability:  Product wants fast rollout, DevOps flags errors
      growth_vs_quality:   Revenue growing but customer satisfaction is low
      total_conflict:      All three disagree on different priorities
    """

    @staticmethod
    def speed_vs_stability() -> List[FeatureFlagObservation]:
        """
        Fast rollout progress + elevated error rate.
        Product is happy (velocity), DevOps is alarmed (errors).
        """
        base = dict(
            feature_name="conflict_speed_stability",
        )
        return [
            FeatureFlagObservation(
                current_rollout_percentage=0.0, error_rate=0.02,
                latency_p99_ms=100.0, user_adoption_rate=0.1,
                revenue_impact=50.0, system_health_score=0.95,
                active_users=2000, time_step=0, **base,
            ),
            FeatureFlagObservation(
                current_rollout_percentage=30.0, error_rate=0.08,
                latency_p99_ms=180.0, user_adoption_rate=0.25,
                revenue_impact=200.0, system_health_score=0.65,
                active_users=5000, time_step=1, **base,
            ),
            FeatureFlagObservation(
                current_rollout_percentage=60.0, error_rate=0.12,
                latency_p99_ms=350.0, user_adoption_rate=0.45,
                revenue_impact=400.0, system_health_score=0.45,
                active_users=8000, time_step=2, **base,
            ),
        ]

    @staticmethod
    def growth_vs_quality() -> List[FeatureFlagObservation]:
        """
        Revenue is growing but customer satisfaction is dropping.
        Product is happy, CustomerSuccess is alarmed.
        """
        base = dict(feature_name="conflict_growth_quality")
        return [
            FeatureFlagObservation(
                current_rollout_percentage=40.0, error_rate=0.06,
                latency_p99_ms=250.0, user_adoption_rate=0.15,
                revenue_impact=600.0, system_health_score=0.55,
                active_users=9000, time_step=0, **base,
            ),
            FeatureFlagObservation(
                current_rollout_percentage=60.0, error_rate=0.09,
                latency_p99_ms=300.0, user_adoption_rate=0.20,
                revenue_impact=800.0, system_health_score=0.45,
                active_users=9500, time_step=1, **base,
            ),
        ]

    @staticmethod
    def total_conflict() -> List[FeatureFlagObservation]:
        """
        All three stakeholders disagree:
        - DevOps: errors critical → wants rollback
        - Product: rollout progressing → wants to push forward
        - CustomerSuccess: some users happy, others complaining → mixed
        """
        return [
            FeatureFlagObservation(
                current_rollout_percentage=45.0, error_rate=0.14,
                latency_p99_ms=380.0, user_adoption_rate=0.35,
                revenue_impact=350.0, system_health_score=0.40,
                active_users=7000, feature_name="conflict_total",
                time_step=0,
            ),
        ]
