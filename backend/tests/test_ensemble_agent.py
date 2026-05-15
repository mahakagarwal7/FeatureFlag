from agents.ensemble_agent import EnsembleAgent
from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation


def make_observation(**overrides) -> FeatureFlagObservation:
    data = {
        "current_rollout_percentage": 40.0,
        "error_rate": 0.03,
        "latency_p99_ms": 140.0,
        "user_adoption_rate": 0.25,
        "revenue_impact": 100.0,
        "system_health_score": 0.88,
        "active_users": 1000,
        "feature_name": "ensemble_test_feature",
        "time_step": 3,
        "reward": 0.0,
        "done": False,
    }
    data.update(overrides)
    return FeatureFlagObservation(**data)


def make_action(action_type: str, target: float, reason: str = "") -> FeatureFlagAction:
    return FeatureFlagAction(action_type=action_type, target_percentage=target, reason=reason)


def test_majority_strategy_picks_major_action(monkeypatch):
    agent = EnsembleAgent(strategy="majority")

    monkeypatch.setattr(agent.rl_agent, "decide", lambda obs, history: make_action("MAINTAIN", 40.0))
    monkeypatch.setattr(agent.baseline_agent, "decide", lambda obs, history: make_action("MAINTAIN", 40.0))
    monkeypatch.setattr(agent.llm_agent, "decide", lambda obs, history: make_action("INCREASE_ROLLOUT", 50.0))

    result = agent.decide(make_observation(), history=[])
    assert result.action_type == "MAINTAIN"
    stats = agent.get_stats()
    assert stats["total_decisions"] == 1
    assert stats["agreement_rate"] == 100.0


def test_rl_with_safety_overrides_unsafe(monkeypatch):
    agent = EnsembleAgent(strategy="rl_with_safety")

    monkeypatch.setattr(agent.rl_agent, "decide", lambda obs, history: make_action("FULL_ROLLOUT", 100.0))
    monkeypatch.setattr(agent.baseline_agent, "decide", lambda obs, history: make_action("DECREASE_ROLLOUT", 20.0))
    monkeypatch.setattr(agent.llm_agent, "decide", lambda obs, history: make_action("MAINTAIN", 40.0))

    obs = make_observation(error_rate=0.20, system_health_score=0.65)
    result = agent.decide(obs, history=[])
    assert result.action_type == "DECREASE_ROLLOUT"
    stats = agent.get_stats()
    assert stats["baseline_wins"] == 1


def test_weighted_strategy_respects_weights(monkeypatch):
    agent = EnsembleAgent(strategy="weighted", weights={"rl": 0.1, "baseline": 0.8, "llm": 0.1})

    monkeypatch.setattr(agent.rl_agent, "decide", lambda obs, history: make_action("INCREASE_ROLLOUT", 50.0))
    monkeypatch.setattr(agent.baseline_agent, "decide", lambda obs, history: make_action("MAINTAIN", 40.0))
    monkeypatch.setattr(agent.llm_agent, "decide", lambda obs, history: make_action("INCREASE_ROLLOUT", 50.0))

    result = agent.decide(make_observation(), history=[])
    assert result.action_type == "MAINTAIN"


def test_confidence_strategy_prefers_rl_when_confident(monkeypatch):
    agent = EnsembleAgent(strategy="confidence")

    monkeypatch.setattr(agent, "_confidence_rl", lambda obs: 0.99)
    monkeypatch.setattr(agent, "_confidence_llm", lambda: 0.10)
    monkeypatch.setattr(agent, "_confidence_baseline", lambda action, obs: 0.20)

    monkeypatch.setattr(agent.rl_agent, "decide", lambda obs, history: make_action("INCREASE_ROLLOUT", 50.0))
    monkeypatch.setattr(agent.baseline_agent, "decide", lambda obs, history: make_action("MAINTAIN", 40.0))
    monkeypatch.setattr(agent.llm_agent, "decide", lambda obs, history: make_action("DECREASE_ROLLOUT", 30.0))

    result = agent.decide(make_observation(), history=[])
    assert result.action_type == "INCREASE_ROLLOUT"
    stats = agent.get_stats()
    assert stats["rl_wins"] == 1
