"""
tests/test_missions.py

Tests for the multi-phase mission system.
Run with: python tests/test_missions.py
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from feature_flag_env.missions import (
    Phase, Mission, MissionTracker, PhaseStatus,
    get_mission, list_missions, MISSION_LIBRARY,
)


def test_mission_library():
    """Mission library should contain pre-built missions."""
    print("🧪 Mission library...")
    missions = list_missions()
    assert len(missions) >= 3, f"Expected ≥3 missions, got {len(missions)}"
    assert "enterprise_payment_gateway" in missions
    assert "quick_ui_update" in missions
    assert "database_migration_mission" in missions
    print(f"   ✅ {len(missions)} missions available")
    return True


def test_get_mission_deep_copy():
    """get_mission should return independent copies."""
    print("🧪 Deep copy test...")
    m1 = get_mission("quick_ui_update")
    m2 = get_mission("quick_ui_update")
    m1.phases[0].name = "MODIFIED"
    assert m2.phases[0].name != "MODIFIED", "Missions should be independent copies"
    print("   ✅ Deep copy confirmed")
    return True


def test_phase_advancement():
    """Tracker should advance phases when exit conditions are met."""
    print("🧪 Phase advancement...")
    mission = Mission(
        name="Test Mission",
        description="Test",
        scenario_name="stable",
        phases=[
            Phase(name="phase1", description="P1",
                  target_rollout_min=0, target_rollout_max=10, max_steps=5, max_error_rate=0.05),
            Phase(name="phase2", description="P2",
                  target_rollout_min=10, target_rollout_max=50, max_steps=10, max_error_rate=0.05),
        ]
    )
    tracker = MissionTracker(mission)
    tracker.reset()

    assert tracker.current_phase.name == "phase1"
    assert tracker.current_phase.status == PhaseStatus.ACTIVE

    # Step within phase1 — not yet at exit
    result = tracker.step(rollout_pct=5.0, error_rate=0.01)
    assert not result["phase_advanced"]
    assert tracker.current_phase.name == "phase1"

    # Step reaching exit of phase1
    result = tracker.step(rollout_pct=10.0, error_rate=0.01)
    assert result["phase_advanced"]
    assert tracker.phases_completed == 1
    assert tracker.current_phase.name == "phase2"

    print("   ✅ Phase advanced correctly")
    return True


def test_phase_failure_error():
    """Phase should fail when error rate exceeds threshold."""
    print("🧪 Phase failure on error...")
    mission = Mission(
        name="Test", description="Test", scenario_name="stable",
        phases=[Phase(name="p1", description="P1",
                      target_rollout_min=0, target_rollout_max=50,
                      max_steps=10, max_error_rate=0.05)]
    )
    tracker = MissionTracker(mission)
    tracker.reset()

    result = tracker.step(rollout_pct=20.0, error_rate=0.10)
    assert result["phase_failed"], "Phase should fail on high errors"
    assert tracker.current_phase.status == PhaseStatus.FAILED
    print("   ✅ Phase failed correctly on errors")
    return True


def test_phase_failure_steps():
    """Phase should fail if steps exhausted without reaching target."""
    print("🧪 Phase failure on step limit...")
    mission = Mission(
        name="Test", description="Test", scenario_name="stable",
        phases=[Phase(name="p1", description="P1",
                      target_rollout_min=0, target_rollout_max=50,
                      max_steps=2, max_error_rate=0.10)]
    )
    tracker = MissionTracker(mission)
    tracker.reset()

    tracker.step(rollout_pct=5.0, error_rate=0.01)
    result = tracker.step(rollout_pct=10.0, error_rate=0.01)  # step 2 = max
    assert result["phase_failed"], "Phase should fail when steps exhausted without target"
    print("   ✅ Phase failed correctly on step limit")
    return True


def test_mission_completion():
    """Mission should complete when all phases pass."""
    print("🧪 Mission completion...")
    mission = Mission(
        name="Test", description="Test", scenario_name="stable",
        phases=[
            Phase(name="p1", description="P1",
                  target_rollout_min=0, target_rollout_max=10, max_steps=5, max_error_rate=0.10),
            Phase(name="p2", description="P2",
                  target_rollout_min=10, target_rollout_max=50, max_steps=5, max_error_rate=0.10),
        ]
    )
    tracker = MissionTracker(mission)
    tracker.reset()

    # Complete phase 1
    result = tracker.step(rollout_pct=10.0, error_rate=0.01)
    assert result["phase_advanced"]

    # Complete phase 2
    result = tracker.step(rollout_pct=50.0, error_rate=0.01)
    assert result["phase_advanced"]
    assert result["mission_complete"]
    assert tracker.is_mission_complete
    print("   ✅ Mission completed")
    return True


def test_stakeholder_gate():
    """Phase with require_stakeholder_approval should block without approval."""
    print("🧪 Stakeholder gate...")
    mission = Mission(
        name="Test", description="Test", scenario_name="stable",
        phases=[Phase(name="gated", description="Gated phase",
                      target_rollout_min=0, target_rollout_max=20,
                      max_steps=10, max_error_rate=0.10,
                      require_stakeholder_approval=True)]
    )
    tracker = MissionTracker(mission)
    tracker.reset()

    # Reach exit target but no approval
    result = tracker.step(rollout_pct=20.0, error_rate=0.01, stakeholder_approval=False)
    assert not result["phase_advanced"], "Should NOT advance without approval"

    # Now with approval
    result = tracker.step(rollout_pct=20.0, error_rate=0.01, stakeholder_approval=True)
    assert result["phase_advanced"], "Should advance with approval"
    print("   ✅ Stakeholder gate works")
    return True


def test_info_dict():
    """to_info_dict should return complete mission snapshot."""
    print("🧪 Info dict...")
    mission = get_mission("quick_ui_update")
    tracker = MissionTracker(mission)
    tracker.reset()

    info = tracker.to_info_dict()
    assert "mission_name" in info
    assert "current_phase" in info
    assert "phase_index" in info
    assert "phase_progress" in info
    assert "phases_completed" in info
    assert "total_phases" in info
    assert info["total_phases"] == 2
    print(f"   ✅ Info dict: {info}")
    return True


# --- Main ------------------------------------------------------------------

def main():
    print("=" * 60)
    print("🚀 MISSION SYSTEM TESTS")
    print("=" * 60)

    results = [
        test_mission_library(),
        test_get_mission_deep_copy(),
        test_phase_advancement(),
        test_phase_failure_error(),
        test_phase_failure_steps(),
        test_mission_completion(),
        test_stakeholder_gate(),
        test_info_dict(),
    ]

    print()
    print("=" * 60)
    if all(results):
        print("✅ ALL MISSION SYSTEM TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED.")
    print("=" * 60)


if __name__ == "__main__":
    main()
