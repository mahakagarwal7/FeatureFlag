"""
tests/test_integration.py

End-to-end integration test with ALL extended features enabled:
- Stakeholders
- Mission phases
- Extended observations
- Extended rewards

Run with: python tests/test_integration.py
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from feature_flag_env.server.feature_flag_environment import FeatureFlagEnvironment
from feature_flag_env.models import FeatureFlagAction


def test_vanilla_backward_compat():
    """Environment with no extensions should behave exactly like before."""
    print("🧪 Vanilla backward compatibility...")
    env = FeatureFlagEnvironment()
    obs = env.reset()

    assert obs.stakeholder_devops_sentiment is None, "No stakeholder fields when disabled"
    assert obs.mission_name is None, "No mission fields when disabled"

    action = FeatureFlagAction(
        action_type="INCREASE_ROLLOUT", target_percentage=10.0, reason="test"
    )
    response = env.step(action)
    assert response.observation.stakeholder_devops_sentiment is None
    assert response.observation.mission_name is None
    assert "mission" not in response.info
    assert "stakeholder_approval" not in response.info

    print("   ✅ Vanilla env unchanged")
    return True


def test_stakeholders_only():
    """Environment with stakeholders but no mission."""
    print("🧪 Stakeholders-only mode...")
    env = FeatureFlagEnvironment(stakeholders_enabled=True)
    obs = env.reset()

    assert obs.stakeholder_devops_sentiment is not None, "DevOps sentiment should be populated"
    assert obs.stakeholder_overall_approval is not None
    assert obs.mission_name is None  # no mission

    action = FeatureFlagAction(
        action_type="INCREASE_ROLLOUT", target_percentage=10.0, reason="test"
    )
    response = env.step(action)
    assert response.observation.stakeholder_devops_sentiment is not None
    assert "stakeholder_approval" in response.info

    print(f"   📊 Sentiments: DevOps={response.observation.stakeholder_devops_sentiment:+.2f}, "
          f"Product={response.observation.stakeholder_product_sentiment:+.2f}, "
          f"CS={response.observation.stakeholder_customer_sentiment:+.2f}")
    print(f"   📊 Overall approval: {response.info['stakeholder_approval']}")
    print("   ✅ Stakeholders populated correctly")
    return True


def test_mission_only():
    """Environment with mission but no stakeholders."""
    print("🧪 Mission-only mode...")
    env = FeatureFlagEnvironment(mission_config="quick_ui_update")
    obs = env.reset()

    assert obs.mission_name is not None, "Mission name should be populated"
    assert obs.current_phase is not None
    assert obs.total_phases == 2
    assert obs.stakeholder_devops_sentiment is None  # no stakeholders

    print(f"   📊 Mission: {obs.mission_name}, Phase: {obs.current_phase}")
    print("   ✅ Mission populated correctly")
    return True


def test_full_episode_all_features():
    """Full episode with stakeholders + mission (quick_ui_update)."""
    print("🧪 Full episode with all features...")
    env = FeatureFlagEnvironment(
        stakeholders_enabled=True,
        mission_config="quick_ui_update",
    )
    obs = env.reset()

    assert obs.mission_name is not None
    assert obs.stakeholder_devops_sentiment is not None

    rollout_targets = [5, 10, 15, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    total_reward = 0.0
    phases_advanced = 0
    steps_taken = 0

    for target in rollout_targets:
        action = FeatureFlagAction(
            action_type="INCREASE_ROLLOUT",
            target_percentage=float(target),
            reason=f"Rolling to {target}%",
        )
        response = env.step(action)
        total_reward += response.reward
        steps_taken += 1

        if response.info.get("phase_advanced"):
            phases_advanced += 1
            print(f"   🎯 Phase advanced at {target}% rollout!")

        if response.done:
            print(f"   ⏹️  Episode done at step {steps_taken} ({target}%): "
                  f"{response.info.get('done_reason', '?')}")
            break

    print(f"   📊 Total reward: {total_reward:+.2f}")
    print(f"   📊 Phases advanced: {phases_advanced}")
    print(f"   📊 Final stakeholder approval: {response.info.get('stakeholder_approval')}")

    # Verify extended observation fields
    final_obs = response.observation
    assert final_obs.stakeholder_devops_sentiment is not None
    assert final_obs.mission_name is not None

    print("   ✅ Full episode completed with all features")
    return True


def test_prompt_string_extended():
    """to_prompt_string should include extended sections when populated."""
    print("🧪 Extended prompt string...")
    env = FeatureFlagEnvironment(
        stakeholders_enabled=True,
        mission_config="quick_ui_update",
    )
    obs = env.reset()
    prompt = obs.to_prompt_string()

    assert "STAKEHOLDER FEEDBACK" in prompt, "Prompt should contain stakeholder section"
    assert "MISSION PROGRESS" in prompt, "Prompt should contain mission section"
    assert "DevOps Sentiment" in prompt

    print(f"   📊 Prompt length: {len(prompt)} chars")
    print("   ✅ Extended prompt sections present")
    return True


def test_enterprise_mission():
    """Enterprise payment gateway — complex multi-phase mission."""
    print("🧪 Enterprise payment gateway mission...")
    env = FeatureFlagEnvironment(
        stakeholders_enabled=True,
        mission_config="enterprise_payment_gateway",
    )
    obs = env.reset()

    assert obs.total_phases == 4
    assert obs.current_phase == "canary"

    # Step through carefully
    rollout_steps = [2, 5, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90, 100]
    steps = 0
    for target in rollout_steps:
        action = FeatureFlagAction(
            action_type="INCREASE_ROLLOUT",
            target_percentage=float(target),
            reason=f"Step to {target}%",
        )
        response = env.step(action)
        steps += 1

        if response.info.get("phase_advanced"):
            phase = response.observation.current_phase
            print(f"   🎯 Phase: {phase} at step {steps} ({target}%)")

        if response.done:
            reason = response.info.get("done_reason", "")
            print(f"   ⏹️  Done: {reason} at step {steps}")
            break

    state = env.state()
    print(f"   📊 Steps: {state.step_count}, Total reward: {state.total_reward:+.2f}")
    print("   ✅ Enterprise mission executed")
    return True


# --- Main ------------------------------------------------------------------

def main():
    print("=" * 60)
    print("🚀 INTEGRATION TESTS — ALL FEATURES")
    print("=" * 60)

    results = [
        test_vanilla_backward_compat(),
        test_stakeholders_only(),
        test_mission_only(),
        test_full_episode_all_features(),
        test_prompt_string_extended(),
        test_enterprise_mission(),
    ]

    print()
    print("=" * 60)
    if all(results):
        print("✅ ALL INTEGRATION TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED.")
    print("=" * 60)


if __name__ == "__main__":
    main()
