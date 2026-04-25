"""
feature_flag_env/missions.py

Multi-phase workflow (mission) system for structured deployments.

A Mission is a named sequence of Phases, each with:
- target rollout range (entry/exit boundaries)
- max steps allowed in that phase
- success criteria (error threshold, stakeholder approval, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class PhaseStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Phase:
    """One stage of a deployment mission."""

    name: str
    description: str

    # Rollout boundaries
    target_rollout_min: float          # entry: rollout must be >= this
    target_rollout_max: float          # exit: advance when rollout >= this

    # Limits
    max_steps: int = 10
    allowed_actions: List[str] = field(
        default_factory=lambda: [
            "INCREASE_ROLLOUT", "DECREASE_ROLLOUT", "MAINTAIN",
            "HALT_ROLLOUT", "ROLLBACK", "FULL_ROLLOUT", "TOOL_CALL"
        ]
    )
    objectives: List[str] = field(default_factory=list)

    # Success criteria
    max_error_rate: float = 0.05       # must stay below this
    require_stakeholder_approval: bool = False

    # Reward weighting for this phase (multiplier on phase-progress reward)
    reward_weight: float = 1.0

    # Runtime state (managed by MissionTracker)
    status: PhaseStatus = PhaseStatus.PENDING
    steps_in_phase: int = 0


@dataclass
class Mission:
    """A complete deployment workflow with ordered phases."""

    name: str
    description: str
    scenario_name: str                 # which scenario to use from scenario_library
    phases: List[Phase] = field(default_factory=list)

    def total_max_steps(self) -> int:
        return sum(p.max_steps for p in self.phases)


# ---------------------------------------------------------------------------
# Mission tracker — runtime state machine
# ---------------------------------------------------------------------------

class MissionTracker:
    """
    Tracks mission progress during an episode.

    Usage:
        tracker = MissionTracker(mission)
        tracker.reset()
        ...
        result = tracker.step(observation, stakeholder_approval)
        if result["phase_advanced"]:
            ...
    """

    def __init__(self, mission: Mission):
        self.mission = mission
        self.current_phase_index: int = 0
        self.phases_completed: int = 0
        self._total_steps: int = 0

    def reset(self) -> None:
        self.current_phase_index = 0
        self.phases_completed = 0
        self._total_steps = 0
        for phase in self.mission.phases:
            phase.status = PhaseStatus.PENDING
            phase.steps_in_phase = 0
        if self.mission.phases:
            self.mission.phases[0].status = PhaseStatus.ACTIVE

    # -- properties ----------------------------------------------------------

    @property
    def current_phase(self) -> Optional[Phase]:
        if self.current_phase_index < len(self.mission.phases):
            return self.mission.phases[self.current_phase_index]
        return None

    @property
    def is_mission_complete(self) -> bool:
        return self.phases_completed >= len(self.mission.phases)

    @property
    def phase_progress(self) -> float:
        """Progress within current phase (0.0 to 1.0)."""
        phase = self.current_phase
        if phase is None:
            return 1.0
        if phase.max_steps == 0:
            return 1.0
        return min(phase.steps_in_phase / phase.max_steps, 1.0)

    @property
    def overall_progress(self) -> float:
        """Overall mission progress (0.0 to 1.0)."""
        if not self.mission.phases:
            return 1.0
        return self.phases_completed / len(self.mission.phases)

    # -- step ----------------------------------------------------------------

    def step(
        self,
        rollout_pct: float,
        error_rate: float,
        stakeholder_approval: bool = True,
    ) -> Dict[str, Any]:
        """
        Advance mission state. Returns a dict with transition info.
        """
        result: Dict[str, Any] = {
            "phase_advanced": False,
            "phase_failed": False,
            "mission_complete": False,
            "current_phase_name": None,
            "phases_completed": self.phases_completed,
        }

        phase = self.current_phase
        if phase is None:
            result["mission_complete"] = True
            return result

        phase.steps_in_phase += 1
        self._total_steps += 1
        result["current_phase_name"] = phase.name

        # --- Check failure: error threshold exceeded ---
        if error_rate > phase.max_error_rate:
            phase.status = PhaseStatus.FAILED
            result["phase_failed"] = True
            return result

        # --- Check failure: ran out of steps in phase ---
        if phase.steps_in_phase >= phase.max_steps:
            # If still within rollout range, count as completed
            if rollout_pct >= phase.target_rollout_max:
                return self._advance_phase(result, stakeholder_approval)
            else:
                phase.status = PhaseStatus.FAILED
                result["phase_failed"] = True
                return result

        # --- Check phase exit condition ---
        if rollout_pct >= phase.target_rollout_max:
            if phase.require_stakeholder_approval and not stakeholder_approval:
                # Can't advance yet — need approval
                return result
            return self._advance_phase(result, stakeholder_approval)

        return result

    def _advance_phase(
        self, result: Dict[str, Any], stakeholder_approval: bool
    ) -> Dict[str, Any]:
        phase = self.current_phase
        if phase is None:
            return result

        phase.status = PhaseStatus.COMPLETED
        self.phases_completed += 1
        self.current_phase_index += 1
        result["phase_advanced"] = True
        result["phases_completed"] = self.phases_completed

        # Activate next phase
        next_phase = self.current_phase
        if next_phase is not None:
            next_phase.status = PhaseStatus.ACTIVE
            result["current_phase_name"] = next_phase.name
        else:
            result["mission_complete"] = True

        return result

    def to_info_dict(self) -> Dict[str, Any]:
        """Snapshot for observation / info dict."""
        phase = self.current_phase
        return {
            "mission_name": self.mission.name,
            "current_phase": phase.name if phase else "COMPLETE",
            "phase_index": self.current_phase_index,
            "phase_progress": self.phase_progress,
            "phases_completed": self.phases_completed,
            "total_phases": len(self.mission.phases),
            "is_mission_complete": self.is_mission_complete,
        }


# ---------------------------------------------------------------------------
# Mission library — pre-built missions
# ---------------------------------------------------------------------------

MISSION_LIBRARY: Dict[str, Mission] = {
    "enterprise_payment_gateway": Mission(
        name="Enterprise Payment Gateway Rollout",
        description="High-stakes payment feature requiring careful phased deployment",
        scenario_name="high_risk",
        phases=[
            Phase(
                name="canary",
                description="Initial canary deployment to 5% of users",
                target_rollout_min=0.0,
                target_rollout_max=5.0,
                max_steps=5,
                allowed_actions=["INCREASE_ROLLOUT", "MAINTAIN", "ROLLBACK", "TOOL_CALL"],
                objectives=["Deploy to internal users", "Validate critical payment pathways with tools"],
                max_error_rate=0.02,
                require_stakeholder_approval=False,
                reward_weight=0.8,
            ),
            Phase(
                name="limited_beta",
                description="Limited beta expansion to 25%",
                target_rollout_min=5.0,
                target_rollout_max=25.0,
                max_steps=10,
                allowed_actions=["INCREASE_ROLLOUT", "DECREASE_ROLLOUT", "MAINTAIN", "HALT_ROLLOUT", "ROLLBACK", "TOOL_CALL"],
                objectives=["Slowly increase rollout", "Gather product/customer feedback"],
                max_error_rate=0.04,
                require_stakeholder_approval=True,
                reward_weight=1.0,
            ),
            Phase(
                name="controlled_expansion",
                description="Controlled expansion to 60%",
                target_rollout_min=25.0,
                target_rollout_max=60.0,
                max_steps=15,
                allowed_actions=["INCREASE_ROLLOUT", "DECREASE_ROLLOUT", "MAINTAIN", "HALT_ROLLOUT", "ROLLBACK", "TOOL_CALL"],
                objectives=["Reach standard traffic capacity", "Ensure robust error handling continues"],
                max_error_rate=0.05,
                require_stakeholder_approval=False,
                reward_weight=1.2,
            ),
            Phase(
                name="full_ga",
                description="Full general availability to 100%",
                target_rollout_min=60.0,
                target_rollout_max=100.0,
                max_steps=10,
                allowed_actions=["INCREASE_ROLLOUT", "DECREASE_ROLLOUT", "MAINTAIN", "HALT_ROLLOUT", "ROLLBACK", "FULL_ROLLOUT", "TOOL_CALL"],
                objectives=["Clear the environment for 100% rollout"],
                max_error_rate=0.05,
                require_stakeholder_approval=True,
                reward_weight=1.5,
            ),
        ],
    ),
    "quick_ui_update": Mission(
        name="Quick UI Update",
        description="Low-risk UI change with rapid 2-phase rollout",
        scenario_name="stable",
        phases=[
            Phase(
                name="beta",
                description="Beta release to 20%",
                target_rollout_min=0.0,
                target_rollout_max=20.0,
                max_steps=5,
                allowed_actions=["INCREASE_ROLLOUT", "MAINTAIN", "ROLLBACK", "TOOL_CALL"],
                objectives=["Fast beta rollout"],
                max_error_rate=0.05,
                require_stakeholder_approval=False,
                reward_weight=1.0,
            ),
            Phase(
                name="full_release",
                description="Full release to 100%",
                target_rollout_min=20.0,
                target_rollout_max=100.0,
                max_steps=10,
                allowed_actions=["INCREASE_ROLLOUT", "MAINTAIN", "ROLLBACK", "FULL_ROLLOUT", "TOOL_CALL"],
                objectives=["Execute the remainder of the release"],
                max_error_rate=0.05,
                require_stakeholder_approval=False,
                reward_weight=1.0,
            ),
        ],
    ),
    "database_migration_mission": Mission(
        name="Database Migration",
        description="Complex database schema migration with multiple safety gates",
        scenario_name="high_risk",
        phases=[
            Phase(
                name="shadow_mode",
                description="Shadow mode testing at 5%",
                target_rollout_min=0.0,
                target_rollout_max=5.0,
                max_steps=8,
                allowed_actions=["INCREASE_ROLLOUT", "MAINTAIN", "TOOL_CALL"],
                objectives=["Ensure zero integration errors using shadow data models", "Validate with Datadog tools"],
                max_error_rate=0.01,
                require_stakeholder_approval=False,
                reward_weight=1.0,
            ),
            Phase(
                name="validation",
                description="Validation phase at 20%",
                target_rollout_min=5.0,
                target_rollout_max=20.0,
                max_steps=10,
                allowed_actions=["INCREASE_ROLLOUT", "DECREASE_ROLLOUT", "MAINTAIN", "HALT_ROLLOUT", "ROLLBACK", "TOOL_CALL"],
                objectives=["Validate small-scale production updates"],
                max_error_rate=0.03,
                require_stakeholder_approval=True,
                reward_weight=1.2,
            ),
            Phase(
                name="migration",
                description="Main migration to 70%",
                target_rollout_min=20.0,
                target_rollout_max=70.0,
                max_steps=15,
                allowed_actions=["INCREASE_ROLLOUT", "DECREASE_ROLLOUT", "MAINTAIN", "HALT_ROLLOUT", "ROLLBACK", "TOOL_CALL"],
                objectives=["Continue schema migration safely"],
                max_error_rate=0.04,
                require_stakeholder_approval=True,
                reward_weight=1.5,
            ),
            Phase(
                name="completion",
                description="Complete migration to 100%",
                target_rollout_min=70.0,
                target_rollout_max=100.0,
                max_steps=10,
                allowed_actions=["INCREASE_ROLLOUT", "DECREASE_ROLLOUT", "MAINTAIN", "HALT_ROLLOUT", "ROLLBACK", "FULL_ROLLOUT", "TOOL_CALL"],
                objectives=["Push remaining traffic to new database"],
                max_error_rate=0.05,
                require_stakeholder_approval=True,
                reward_weight=1.5,
            ),
        ],
    ),
}


def get_mission(mission_name: str) -> Mission:
    """Get a mission by name. Returns a deep copy."""
    if mission_name not in MISSION_LIBRARY:
        available = ", ".join(MISSION_LIBRARY.keys())
        raise ValueError(
            f"Unknown mission: {mission_name}. Available: {available}"
        )
    import copy
    return copy.deepcopy(MISSION_LIBRARY[mission_name])


def list_missions() -> List[str]:
    """Return available mission names."""
    return list(MISSION_LIBRARY.keys())
