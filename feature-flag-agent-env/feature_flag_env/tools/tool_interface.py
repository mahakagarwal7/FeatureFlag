"""
feature_flag_env/tools/tool_interface.py

Unified Tool Interface Layer.

Provides:
- Tool: Abstract base class with call/validate/parse_response lifecycle
- ToolResult: Standardized result from any tool call
- ToolCallRequest: Agent's request to invoke a tool
- ValidationResult: Pre-call validation outcome
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ToolResult(BaseModel):
    """Standardized result from any tool call."""

    success: bool
    tool_name: str
    action_name: str
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: float = 0.0
    timestamp: float = Field(default_factory=time.time)

    @property
    def summary(self) -> str:
        if self.success:
            return f"[{self.tool_name}.{self.action_name}] OK ({self.latency_ms:.0f}ms)"
        return f"[{self.tool_name}.{self.action_name}] FAILED: {self.error}"


class ToolCallRequest(BaseModel):
    """Agent's request to invoke a specific tool action."""

    tool_name: str             # "github", "datadog", "slack"
    action_name: str           # "get_deployment_status", "get_error_rate", etc.
    params: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Result of pre-call validation."""

    valid: bool
    errors: List[str] = Field(default_factory=list)


class ToolMode(str, Enum):
    """Whether a tool uses mock (simulated) or real (API) backend."""
    MOCK = "mock"
    REAL = "real"


# ---------------------------------------------------------------------------
# Abstract Tool base class
# ---------------------------------------------------------------------------

class Tool(ABC):
    """
    Abstract base class for all environment-integrated tools.

    Lifecycle per call:
        1. validate(action_name, params) → ValidationResult
        2. call(action_name, params) → ToolResult
           internally calls: raw = _execute(...)
                             parsed = parse_response(raw)
        3. Result stored in ToolManager memory

    Subclasses implement:
        - _execute(action_name, params) → dict
        - parse_response(action_name, raw) → dict
        - validate(action_name, params) → ValidationResult
    """

    def __init__(
        self,
        name: str,
        mode: ToolMode,
        available_actions: List[str],
        timeout_ms: float = 5000.0,
        max_calls_per_episode: int = 50,
        **kwargs,
    ):
        self.name = name
        self.mode = mode
        self.available_actions = available_actions
        self.timeout_ms = timeout_ms
        self.max_calls_per_episode = max_calls_per_episode

        # Runtime metrics
        self.call_count: int = 0
        self.error_count: int = 0
        self.total_latency_ms: float = 0.0
        self._last_error: Optional[str] = None

    # -- public API ----------------------------------------------------------

    def call(self, action_name: str, params: Dict[str, Any] = None) -> ToolResult:
        """
        Execute a tool action with validation, timing, and error handling.
        """
        params = params or {}

        # Rate limit check
        if self.call_count >= self.max_calls_per_episode:
            return self._error_result(
                action_name, f"Rate limit exceeded ({self.max_calls_per_episode} calls/episode)"
            )

        # Validate
        validation = self.validate(action_name, params)
        if not validation.valid:
            return self._error_result(
                action_name, f"Validation failed: {'; '.join(validation.errors)}"
            )

        # Execute with timing
        start = time.time()
        try:
            raw = self._execute(action_name, params)
            elapsed_ms = (time.time() - start) * 1000

            # Timeout check (simulated — real timeouts handled in _execute)
            if elapsed_ms > self.timeout_ms:
                self.error_count += 1
                self.call_count += 1
                self._last_error = "timeout"
                return ToolResult(
                    success=False,
                    tool_name=self.name,
                    action_name=action_name,
                    error=f"Timeout: {elapsed_ms:.0f}ms exceeded {self.timeout_ms:.0f}ms limit",
                    latency_ms=elapsed_ms,
                )

            parsed = self.parse_response(action_name, raw)

            self.call_count += 1
            self.total_latency_ms += elapsed_ms

            return ToolResult(
                success=True,
                tool_name=self.name,
                action_name=action_name,
                data=parsed,
                latency_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            self.call_count += 1
            self.error_count += 1
            self._last_error = str(e)
            return self._error_result(action_name, str(e), elapsed_ms)

    def validate(self, action_name: str, params: Dict[str, Any]) -> ValidationResult:
        """
        Default validation: check action_name is known.
        Subclasses can override for param-level validation.
        """
        errors = []
        if action_name not in self.available_actions:
            errors.append(
                f"Unknown action '{action_name}'. Available: {self.available_actions}"
            )
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def reset(self) -> None:
        """Reset per-episode counters."""
        self.call_count = 0
        self.error_count = 0
        self.total_latency_ms = 0.0
        self._last_error = None

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "tool": self.name,
            "mode": self.mode.value,
            "calls": self.call_count,
            "errors": self.error_count,
            "avg_latency_ms": (
                self.total_latency_ms / self.call_count if self.call_count > 0 else 0.0
            ),
            "last_error": self._last_error,
        }

    # -- to be implemented by subclasses -------------------------------------

    @abstractmethod
    def _execute(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Internal: perform the actual tool action. Returns raw response dict."""
        ...

    def parse_response(self, action_name: str, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse/normalize raw response. Default: pass-through.
        Subclasses can override for custom parsing.
        """
        return raw

    # -- helpers -------------------------------------------------------------

    def _error_result(
        self, action_name: str, error: str, latency_ms: float = 0.0
    ) -> ToolResult:
        return ToolResult(
            success=False,
            tool_name=self.name,
            action_name=action_name,
            error=error,
            latency_ms=latency_ms,
        )
