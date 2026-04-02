import os
import sys
from types import SimpleNamespace

import pytest
from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation
from agents.llm_agent import LLMAgent
from agents.hybrid_agent import HybridAgent


def make_observation(**overrides) -> FeatureFlagObservation:
    data = {
        "current_rollout_percentage": 40.0,
        "error_rate": 0.05,
        "latency_p99_ms": 150.0,
        "user_adoption_rate": 0.25,
        "revenue_impact": 1200.0,
        "system_health_score": 0.85,
        "active_users": 1000,
        "feature_name": "TestFeature",
        "time_step": 5,
        "reward": 0.0,
        "done": False,
    }
    data.update(overrides)
    return FeatureFlagObservation(**data)


def test_parse_llm_json_handles_json_block_and_python_dict():
    agent = LLMAgent()

    json_block = '```json\n{"action_type": "FULL_ROLLOUT", "target_percentage": 100}\n```'
    assert agent._parse_llm_json(json_block) == {
        "action_type": "FULL_ROLLOUT",
        "target_percentage": 100,
    }

    python_dict = "{'action_type': 'ROLLBACK', 'target_percentage': 0}"
    assert agent._parse_llm_json(python_dict) == {
        "action_type": "ROLLBACK",
        "target_percentage": 0,
    }


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("increase", "INCREASE_ROLLOUT"),
        ("CONTINUE_ROLLOUT", "INCREASE_ROLLOUT"),
        ("scale_down", "DECREASE_ROLLOUT"),
        ("keep", "MAINTAIN"),
        ("pause", "HALT_ROLLOUT"),
        ("full", "FULL_ROLLOUT"),
        ("rollback_all", "ROLLBACK"),
        ("unknown action", "MAINTAIN"),
    ],
)
def test_normalize_action_type_aliases(raw, expected):
    agent = LLMAgent()
    assert agent._normalize_action_type(raw) == expected


def test_resolve_target_percentage_defaults_for_actions():
    agent = LLMAgent()
    assert agent._resolve_target_percentage(None, "INCREASE_ROLLOUT", 40.0) == 50.0
    assert agent._resolve_target_percentage(None, "DECREASE_ROLLOUT", 40.0) == 30.0
    assert agent._resolve_target_percentage(None, "MAINTAIN", 40.0) == 40.0
    assert agent._resolve_target_percentage(None, "FULL_ROLLOUT", 40.0) == 100.0
    assert agent._resolve_target_percentage(None, "ROLLBACK", 40.0) == 0.0


def test_decide_falls_back_to_baseline_when_no_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    agent = LLMAgent()
    assert agent.use_baseline

    obs = make_observation(error_rate=0.0, current_rollout_percentage=20.0)
    action = agent.decide(obs, history=[])

    assert isinstance(action, FeatureFlagAction)
    assert action.action_type == "INCREASE_ROLLOUT"
    assert action.target_percentage == 30.0


def test_decide_uses_groq_client_with_mocked_response(monkeypatch):
    dummy_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"action_type": "DECREASE_ROLLOUT", "target_percentage": 30, "reason": "High error risk"}'
                )
            )
        ]
    )

    class FakeCompletions:
        def __init__(self):
            self.calls = []

        def create(self, model, messages, temperature, response_format):
            self.calls.append({
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "response_format": response_format,
            })
            return dummy_response

    class FakeGroq:
        def __init__(self, api_key, timeout):
            self.api_key = api_key
            self.timeout = timeout
            self.chat = SimpleNamespace(completions=FakeCompletions())

    fake_groq_module = SimpleNamespace(Groq=FakeGroq)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_TIMEOUT_SECONDS", "10")
    monkeypatch.syspath_prepend(os.path.dirname(__file__))
    sys.modules["groq"] = fake_groq_module

    agent = LLMAgent(model="test-model")
    assert not agent.use_baseline
    assert hasattr(agent, "client")

    obs = make_observation(current_rollout_percentage=60.0)
    action = agent.decide(obs, history=[])

    assert action.action_type == "DECREASE_ROLLOUT"
    assert action.target_percentage == 30.0
    assert action.reason == "High error risk"
    assert agent.api_calls == 1
    assert agent.api_failures == 0


def test_decide_with_real_groq_api():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        pytest.skip("GROQ_API_KEY not set in environment")

    try:
        import groq  # noqa: F401
    except ImportError:
        pytest.skip("groq package is not installed")

    agent = LLMAgent()
    if agent.use_baseline:
        pytest.skip("LLMAgent is using baseline fallback despite GROQ_API_KEY")

    obs = make_observation(current_rollout_percentage=40.0, error_rate=0.02)
    action = agent.decide(obs, history=[])

    assert action.action_type in {
        "INCREASE_ROLLOUT",
        "DECREASE_ROLLOUT",
        "MAINTAIN",
        "HALT_ROLLOUT",
        "FULL_ROLLOUT",
        "ROLLBACK",
    }
    assert 0.0 <= action.target_percentage <= 100.0
    assert action.reason
    assert action.reason != "LLM decision"


def test_decide_recovery_on_api_error(monkeypatch):
    class ErrorCompletions:
        def create(self, *args, **kwargs):
            raise RuntimeError("API failed")

    class ErrorGroq:
        def __init__(self, api_key, timeout):
            self.chat = SimpleNamespace(completions=ErrorCompletions())

    fake_groq_module = SimpleNamespace(Groq=ErrorGroq)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_TIMEOUT_SECONDS", "10")
    sys.modules["groq"] = fake_groq_module

    agent = LLMAgent()
    obs = make_observation(error_rate=0.20, current_rollout_percentage=60.0)
    action = agent.decide(obs, history=[])

    assert action.action_type == "ROLLBACK"
    assert action.target_percentage == 0.0
    assert agent.api_calls == 1
    assert agent.api_failures == 1
    assert "API failed" in agent.last_error


def test_hybrid_agent_safety_override(monkeypatch):
    hybrid = HybridAgent()

    monkeypatch.setattr(
        hybrid.llm,
        "decide",
        lambda observation, history: FeatureFlagAction(
            action_type="INCREASE_ROLLOUT",
            target_percentage=90.0,
            reason="LLM proposed increase"
        ),
    )

    obs = make_observation(error_rate=0.20, current_rollout_percentage=70.0)
    action = hybrid.decide(obs, history=[])

    assert action.action_type != "INCREASE_ROLLOUT"
    assert action.reason.startswith("Safety override")
    assert hybrid.safety_overrides == 1
