"""
feature_flag_env/tools/base_tools.py

Abstract base class for external tool integrations.
Extensible architecture for GitHub, Slack, PagerDuty, Datadog, etc.
"""

from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from enum import Enum


class ToolStatus(str, Enum):
    """Status of tool integration"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    UNINITIALIZED = "uninitialized"


class ToolResponse(BaseModel):
    """Standardized response from any external tool"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ExternalToolsInterface(ABC):
    """
    Abstract base class for external tool integrations.
    
    Example implementations:
    - GitHubClient (see github_integration.py)
    - SlackClient (future)
    - DatadogClient (future)
    """
    
    def __init__(self, tool_name: str, credentials: Optional[Dict[str, str]] = None):
        self.tool_name = tool_name
        self.credentials = credentials or {}
        self.status = ToolStatus.UNINITIALIZED
        self.last_error: Optional[str] = None
        self.call_count = 0
        self.error_count = 0
    
    @abstractmethod
    def authenticate(self) -> ToolResponse:
        """
        Authenticate with the external service.
        Must be called before using the tool.
        """
        pass
    
    @abstractmethod
    def get_status(self) -> ToolStatus:
        """Get current connection status"""
        pass
    
    def _record_call(self, success: bool, error: Optional[str] = None):
        """Internal: Track API calls for metrics"""
        self.call_count += 1
        if not success:
            self.error_count += 1
            self.last_error = error
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get usage metrics"""
        return {
            "tool": self.tool_name,
            "status": self.status.value,
            "total_calls": self.call_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / self.call_count if self.call_count > 0 else 0.0,
            "last_error": self.last_error,
        }
