import pytest

from agents.human_in_loop_agent import HumanInLoopAgent
from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation


def make_observation(**overrides) -> FeatureFlagObservation:
    data = {
        "current_rollout_percentage": 40.0,
        "error_rate": 0.03,
        "latency_p99_ms": 120.0,
        "user_adoption_rate": 0.35,
        "revenue_impact": 200.0,
        "system_health_score": 0.9,
        "active_users": 1000,
        "feature_name": "hitl_test_feature",
        "time_step": 5,
        "reward": 0.0,
        "done": False,
    }
    data.update(overrides)
    return FeatureFlagObservation(**data)


def test_hitl_auto_approve_when_confident(monkeypatch):
    agent = HumanInLoopAgent(confidence_threshold=0.7, allow_human_prompt=False)

    suggested = FeatureFlagAction(
        action_type="INCREASE_ROLLOUT",
        target_percentage=50.0,
        reason="RL suggestion",
    )

    monkeypatch.setattr(agent, "_rl_suggest_action", lambda obs: (suggested, 0.91))

    action = agent.decide(make_observation(), history=[])

    assert action.action_type == "INCREASE_ROLLOUT"
    assert action.target_percentage == 50.0
    assert "auto-approved" in action.reason


def test_hitl_noninteractive_baseline_fallback(monkeypatch):
    agent = HumanInLoopAgent(
        confidence_threshold=0.8,
        non_interactive_action="baseline",
        allow_human_prompt=False,
    )

    suggested = FeatureFlagAction(
        action_type="FULL_ROLLOUT",
        target_percentage=100.0,
        reason="RL suggestion",
    )

    baseline_action = FeatureFlagAction(
        action_type="MAINTAIN",
        target_percentage=40.0,
        reason="baseline",
    )

    monkeypatch.setattr(agent, "_rl_suggest_action", lambda obs: (suggested, 0.12))
    monkeypatch.setattr(agent.baseline_agent, "decide", lambda obs, history: baseline_action)

    action = agent.decide(make_observation(), history=[])

    assert action.action_type == "MAINTAIN"
    assert action.target_percentage == 40.0
    assert "non-interactive mode" in action.reason


def test_hitl_noninteractive_approve(monkeypatch):
    agent = HumanInLoopAgent(
        confidence_threshold=0.95,
        non_interactive_action="approve",
        allow_human_prompt=False,
    )

    suggested = FeatureFlagAction(
        action_type="DECREASE_ROLLOUT",
        target_percentage=20.0,
        reason="RL suggestion",
    )

    monkeypatch.setattr(agent, "_rl_suggest_action", lambda obs: (suggested, 0.30))

    action = agent.decide(make_observation(), history=[])

    assert action.action_type == "DECREASE_ROLLOUT"
    assert action.target_percentage == 20.0
    assert "non-interactive mode" in action.reason
