"""
feature_flag_env/tools/tool_manager.py

ToolManager — orchestrator for tool registration, dispatch, and memory.

Maintains a registry of available tools and a rolling buffer of recent
tool call results (ToolMemory) that feeds into the observation space.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional

from .tool_interface import Tool, ToolCallRequest, ToolResult


# ---------------------------------------------------------------------------
# ToolMemory — rolling buffer of recent results
# ---------------------------------------------------------------------------

class ToolMemory:
    """Fixed-size rolling buffer of recent tool results."""

    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self._buffer: deque[ToolResult] = deque(maxlen=max_size)

    def add(self, result: ToolResult) -> None:
        self._buffer.append(result)

    def clear(self) -> None:
        self._buffer.clear()

    @property
    def recent(self) -> List[ToolResult]:
        return list(self._buffer)

    @property
    def last(self) -> Optional[ToolResult]:
        return self._buffer[-1] if self._buffer else None

    def summary(self) -> Dict[str, Any]:
        """Compact summary for observation injection."""
        if not self._buffer:
            return {
                "total_calls": 0,
                "recent_results": [],
                "tools_used": [],
            }

        return {
            "total_calls": len(self._buffer),
            "recent_results": [
                {
                    "tool": r.tool_name,
                    "action": r.action_name,
                    "success": r.success,
                    "summary": r.summary,
                }
                for r in list(self._buffer)[-5:]  # last 5
            ],
            "tools_used": list({r.tool_name for r in self._buffer}),
            "error_count": sum(1 for r in self._buffer if not r.success),
        }


# ---------------------------------------------------------------------------
# ToolManager — orchestrator
# ---------------------------------------------------------------------------

class ToolManager:
    """
    Manages tool registration, dispatch, and state for the environment.

    Usage:
        manager = ToolManager()
        manager.register(MockGitHubTool())
        manager.register(MockDatadogTool())
        manager.register(MockSlackTool())

        result = manager.execute(ToolCallRequest(
            tool_name="github",
            action_name="get_deployment_status",
            params={"environment": "production"},
        ))
    """

    def __init__(self, memory_size: int = 20):
        self._tools: Dict[str, Tool] = {}
        self.memory = ToolMemory(max_size=memory_size)

    def register(self, tool: Tool) -> None:
        """Register a tool by its name."""
        self._tools[tool.name] = tool

    def unregister(self, tool_name: str) -> None:
        self._tools.pop(tool_name, None)

    @property
    def tool_names(self) -> List[str]:
        return list(self._tools.keys())

    @property
    def connected_count(self) -> int:
        return len(self._tools)

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def reset(self) -> None:
        """Reset all tools and memory for a new episode."""
        self.memory.clear()
        for tool in self._tools.values():
            tool.reset()

    def execute(self, request: ToolCallRequest) -> ToolResult:
        """
        Dispatch a tool call request to the appropriate tool.

        Returns ToolResult (always — errors are wrapped, never raised).
        """
        tool = self._tools.get(request.tool_name)
        if tool is None:
            result = ToolResult(
                success=False,
                tool_name=request.tool_name,
                action_name=request.action_name,
                error=f"Unknown tool: '{request.tool_name}'. Available: {self.tool_names}",
            )
            self.memory.add(result)
            return result

        result = tool.call(request.action_name, request.params)
        self.memory.add(result)
        return result

    def update_env_state(self, state: Dict[str, Any]) -> None:
        """
        Propagate current environment state to mock tools
        so they can generate realistic responses.
        """
        for tool in self._tools.values():
            if hasattr(tool, "set_env_state"):
                tool.set_env_state(state)

    def get_state(self) -> Dict[str, Any]:
        """Full snapshot for enriching observations."""
        return {
            "connected_tools": self.connected_count,
            "tool_names": self.tool_names,
            "tools_used_this_episode": sum(t.call_count for t in self._tools.values()),
            "total_errors": sum(t.error_count for t in self._tools.values()),
            "memory": self.memory.summary(),
            "tool_metrics": {
                name: tool.get_metrics() for name, tool in self._tools.items()
            },
        }

    def get_last_result_dict(self) -> Optional[Dict[str, Any]]:
        """Return the last tool result as a serializable dict (for observation)."""
        last = self.memory.last
        if last is None:
            return None
        return {
            "tool": last.tool_name,
            "action": last.action_name,
            "success": last.success,
            "data": last.data,
            "error": last.error,
            "latency_ms": last.latency_ms,
        }

    def available_actions_summary(self) -> Dict[str, List[str]]:
        """Return available actions per tool (for agent prompt injection)."""
        return {
            name: tool.available_actions
            for name, tool in self._tools.items()
        }
