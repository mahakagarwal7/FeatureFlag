"""
tests/test_tool_interface.py

Tests for the Tool Integration Layer:
- Tool interface / lifecycle
- Mock adapters
- ToolManager (dispatch + memory)
- Environment TOOL_CALL action
- Failure handling (validation, rate limiting, unknown tool)

Run with: python tests/test_tool_interface.py
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from feature_flag_env.tools.tool_interface import Tool, ToolResult, ToolCallRequest, ToolMode, ValidationResult
from feature_flag_env.tools.mock_adapters import MockGitHubTool, MockSlackTool
from feature_flag_env.tools.tool_manager import ToolManager, ToolMemory
from feature_flag_env.server.feature_flag_environment import FeatureFlagEnvironment
from feature_flag_env.models import FeatureFlagAction


# ===========================================================================
# Tool Interface Tests
# ===========================================================================

def test_mock_github_tool():
    """MockGitHubTool should return simulated responses."""
    print("🧪 MockGitHubTool basic...")
    tool = MockGitHubTool()
    tool.set_env_state({"error_rate": 0.02, "rollout_percentage": 30.0})

    result = tool.call("get_deployment_status", {"environment": "production"})
    assert result.success, f"Expected success, got error: {result.error}"
    assert result.tool_name == "github"
    assert result.action_name == "get_deployment_status"
    assert "status" in result.data
    assert result.latency_ms >= 0

    print(f"   📊 Deployment status: {result.data['status']}")
    print("   ✅ Passed")


def test_mock_slack_tool():
    """MockSlackTool should log messages."""
    print("🧪 MockSlackTool basic...")
    tool = MockSlackTool()

    result = tool.call("send_message", {"channel": "#deployments", "text": "Hello"})
    assert result.success
    assert len(tool.message_log) == 1
    assert tool.message_log[0]["text"] == "Hello"

    result2 = tool.call("send_rollout_update", {
        "channel": "#deployments",
        "feature_name": "checkout-v2",
        "action": "INCREASE_ROLLOUT",
        "percentage": 40,
    })
    assert result2.success
    assert len(tool.message_log) == 2

    print(f"   📊 Messages logged: {len(tool.message_log)}")
    print("   ✅ Passed")


# ===========================================================================
# Validation Tests
# ===========================================================================

def test_validation_unknown_action():
    """Should reject unknown action names."""
    print("🧪 Validation: unknown action...")
    tool = MockGitHubTool()
    result = tool.call("nonexistent_action", {})
    assert not result.success
    assert "Unknown action" in result.error

    print(f"   📊 Error: {result.error}")
    print("   ✅ Passed")


def test_validation_missing_params():
    """Should reject calls with missing required params."""
    print("🧪 Validation: missing params...")

    slack = MockSlackTool()
    result = slack.call("send_message", {})  # missing channel
    assert not result.success
    assert "channel" in result.error

    print("   ✅ Passed")


def test_rate_limiting():
    """Should reject calls after rate limit exceeded."""
    print("🧪 Rate limiting...")
    tool = MockGitHubTool(max_calls_per_episode=3)
    tool.set_env_state({"error_rate": 0.02, "rollout_percentage": 10.0})

    for i in range(3):
        result = tool.call("get_deployment_status", {"environment": "production"})
        assert result.success, f"Call {i+1} should succeed"

    # 4th call should fail
    result = tool.call("get_deployment_status", {"environment": "production"})
    assert not result.success
    assert "Rate limit" in result.error

    print(f"   📊 Calls made: {tool.call_count}")
    print("   ✅ Passed")


def test_metrics_tracking():
    """Tool should track call count, errors, latency."""
    print("🧪 Metrics tracking...")
    tool = MockGitHubTool()
    tool.set_env_state({"error_rate": 0.02, "rollout_percentage": 10.0})

    tool.call("get_deployment_status", {"environment": "production"})
    tool.call("get_cicd_status", {"branch": "main"})
    tool.call("bogus_action", {})  # validation failure — NOT counted in call_count

    metrics = tool.get_metrics()
    # Only successful calls go through _execute and increment call_count
    assert metrics["calls"] == 2, f"Expected 2 calls, got {metrics['calls']}"
    assert metrics["errors"] == 0, f"Expected 0 execution errors, got {metrics['errors']}"
    assert metrics["avg_latency_ms"] >= 0

    print(f"   📊 Metrics: {metrics}")
    print("   ✅ Passed")


# ===========================================================================
# ToolManager Tests
# ===========================================================================

def test_tool_manager_register():
    """ToolManager should register and dispatch tools."""
    print("🧪 ToolManager register + dispatch...")
    manager = ToolManager()
    manager.register(MockGitHubTool())
    manager.register(MockSlackTool())

    assert manager.connected_count == 2
    assert "github" in manager.tool_names

    manager.update_env_state({"error_rate": 0.02, "latency_p99_ms": 100, "rollout_percentage": 10})

    result = manager.execute(ToolCallRequest(
        tool_name="github",
        action_name="get_deployment_status",
        params={"environment": "production"},
    ))
    assert result.success

    print(f"   📊 Connected tools: {manager.tool_names}")
    print("   ✅ Passed")


def test_tool_manager_unknown_tool():
    """ToolManager should return error for unknown tool."""
    print("🧪 ToolManager: unknown tool...")
    manager = ToolManager()
    manager.register(MockGitHubTool())

    result = manager.execute(ToolCallRequest(
        tool_name="pagerduty",
        action_name="get_incidents",
    ))
    assert not result.success
    assert "Unknown tool" in result.error

    print(f"   📊 Error: {result.error}")
    print("   ✅ Passed")


def test_tool_memory():
    """ToolMemory should maintain rolling buffer."""
    print("🧪 ToolMemory buffer...")
    manager = ToolManager(memory_size=3)
    manager.register(MockGitHubTool())
    manager.update_env_state({"error_rate": 0.02, "rollout_percentage": 10})

    for i in range(5):
        manager.execute(ToolCallRequest(
            tool_name="github",
            action_name="get_deployment_status",
            params={"environment": "production"},
        ))

    assert len(manager.memory.recent) == 3  # capped at 3
    summary = manager.memory.summary()
    assert summary["total_calls"] == 3  # buffer only holds 3
    assert len(summary["recent_results"]) <= 5

    print(f"   📊 Buffer size: {len(manager.memory.recent)}")
    print("   ✅ Passed")


def test_tool_manager_reset():
    """ToolManager.reset() should clear memory and tool counters."""
    print("🧪 ToolManager reset...")
    manager = ToolManager()
    github = MockGitHubTool()
    manager.register(github)
    manager.update_env_state({"error_rate": 0.02, "rollout_percentage": 10})

    manager.execute(ToolCallRequest(
        tool_name="github", action_name="get_deployment_status", params={"environment": "prod"},
    ))
    assert github.call_count == 1

    manager.reset()
    assert github.call_count == 0
    assert manager.memory.last is None

    print("   ✅ Passed")


# ===========================================================================
# Environment Integration Tests
# ===========================================================================

def test_env_tool_call_action():
    """Environment should handle TOOL_CALL action type."""
    print("🧪 Environment TOOL_CALL action...")
    env = FeatureFlagEnvironment(tools_enabled=True)
    obs = env.reset()

    action = FeatureFlagAction(
        action_type="TOOL_CALL",
        target_percentage=0.0,
        reason="Check deployment status",
        tool_call={
            "tool_name": "github",
            "action_name": "get_deployment_status",
            "params": {"environment": "production"},
        },
    )
    response = env.step(action)

    assert response.observation.last_tool_result is not None
    assert response.observation.last_tool_result["tool"] == "github"
    assert response.observation.last_tool_result["success"] is True
    assert "tool_call_result" in response.info

    print(f"   📊 Tool result: {response.observation.last_tool_result['action']}")
    print(f"   📊 Reward: {response.reward:+.2f}")
    print("   ✅ Passed")


def test_env_tool_call_prompt_string():
    """Observation prompt should include LAST TOOL RESULT section."""
    print("🧪 TOOL_CALL prompt string...")
    env = FeatureFlagEnvironment(tools_enabled=True)
    env.reset()

    action = FeatureFlagAction(
        action_type="TOOL_CALL",
        target_percentage=0.0,
        reason="Check metrics",
        tool_call={
            "tool_name": "github",
            "action_name": "get_cicd_status",
            "params": {"branch": "main"},
        },
    )
    response = env.step(action)
    prompt = response.observation.to_prompt_string()

    assert "LAST TOOL RESULT" in prompt
    assert "github" in prompt

    print(f"   📊 Prompt length: {len(prompt)} chars")
    print("   ✅ Passed")


def test_env_mixed_actions():
    """Environment should handle mix of regular and TOOL_CALL actions."""
    print("🧪 Mixed regular + TOOL_CALL actions...")
    env = FeatureFlagEnvironment(tools_enabled=True)
    env.reset()

    # Regular rollout action
    r1 = env.step(FeatureFlagAction(
        action_type="INCREASE_ROLLOUT", target_percentage=10.0, reason="test",
    ))
    assert r1.observation.last_tool_result is None  # no tool call

    # Tool call action
    r2 = env.step(FeatureFlagAction(
        action_type="TOOL_CALL", target_percentage=0.0, reason="check",
        tool_call={"tool_name": "github", "action_name": "get_cicd_status", "params": {"branch": "main"}},
    ))
    assert r2.observation.last_tool_result is not None
    # Rollout should NOT have changed
    assert r2.observation.current_rollout_percentage == 10.0

    # Another regular action
    r3 = env.step(FeatureFlagAction(
        action_type="INCREASE_ROLLOUT", target_percentage=20.0, reason="test",
    ))
    assert r3.observation.current_rollout_percentage == 20.0

    print(f"   📊 Rollout: 0 → 10 → 10 (tool) → 20")
    print("   ✅ Passed")


def test_env_tools_disabled():
    """With tools_enabled=False, TOOL_CALL should still work but with penalty."""
    print("🧪 TOOL_CALL with tools disabled...")
    env = FeatureFlagEnvironment(tools_enabled=False)
    env.reset()

    action = FeatureFlagAction(
        action_type="TOOL_CALL", target_percentage=0.0, reason="test",
        tool_call={"tool_name": "github", "action_name": "get_deployment_status", "params": {}},
    )
    response = env.step(action)
    # Should penalize since tool manager is not initialized
    assert response.reward < 0, f"Expected negative reward, got {response.reward}"

    print(f"   📊 Penalty reward: {response.reward:+.2f}")
    print("   ✅ Passed")


def test_env_tool_call_invalid():
    """Invalid tool call should return error result."""
    print("🧪 Invalid tool call...")
    env = FeatureFlagEnvironment(tools_enabled=True)
    env.reset()

    action = FeatureFlagAction(
        action_type="TOOL_CALL", target_percentage=0.0, reason="test",
        tool_call={"tool_name": "nonexistent", "action_name": "foo", "params": {}},
    )
    response = env.step(action)
    assert response.observation.last_tool_result is not None
    assert response.observation.last_tool_result["success"] is False
    assert response.reward < 0

    print(f"   📊 Error: {response.observation.last_tool_result['error']}")
    print("   ✅ Passed")


# ===========================================================================
# Backward Compatibility
# ===========================================================================

def test_backward_compat():
    """Existing tests should still work (no tools enabled)."""
    print("🧪 Backward compatibility...")
    env = FeatureFlagEnvironment()
    obs = env.reset()

    assert obs.last_tool_result is None
    assert obs.tool_memory_summary is None

    action = FeatureFlagAction(
        action_type="INCREASE_ROLLOUT", target_percentage=15.0, reason="test",
    )
    response = env.step(action)
    assert response.observation.last_tool_result is None
    assert response.observation.current_rollout_percentage == 15.0

    print("   ✅ Passed")


# ===========================================================================
# Main
# ===========================================================================

def main():
    print("=" * 60)
    print("🚀 TOOL INTEGRATION LAYER TESTS")
    print("=" * 60)

    results = [
        # Tool interface
        test_mock_github_tool(),
        test_mock_slack_tool(),

        # Validation & failure
        test_validation_unknown_action(),
        test_validation_missing_params(),
        test_rate_limiting(),
        test_metrics_tracking(),

        # ToolManager
        test_tool_manager_register(),
        test_tool_manager_unknown_tool(),
        test_tool_memory(),
        test_tool_manager_reset(),

        # Environment integration
        test_env_tool_call_action(),
        test_env_tool_call_prompt_string(),
        test_env_mixed_actions(),
        test_env_tools_disabled(),
        test_env_tool_call_invalid(),
        test_backward_compat(),
    ]

    print()
    print("=" * 60)
    if all(results):
        print(f"✅ ALL {len(results)} TOOL INTEGRATION TESTS PASSED!")
    else:
        failed = sum(1 for r in results if not r)
        print(f"❌ {failed} TEST(S) FAILED.")
    print("=" * 60)


if __name__ == "__main__":
    main()
