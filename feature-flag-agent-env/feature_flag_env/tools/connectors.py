"""
feature_flag_env/tools/connectors.py

Connector Framework Extension.
Provides low-level network/API abstraction (Connectors) which can be optionally dynamically wrapped
by higher-level lifecycle handlers (Tools) to enforce backward compatibility and tracking.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import time


class Connector(ABC):
    """
    Abstract Base Class for pure data-fetching and action-dispatching integrations.
    Unlike Tools, Connectors do not track per-episode metrics, maintain local error limits,
    or validate high-level environment actions. They purely connect to APIs.
    """

    def __init__(self, name: str, base_url: str, api_key: Optional[str] = None):
        self.name = name
        self.base_url = base_url
        self.api_key = api_key
        self.is_connected = False

    def connect(self) -> bool:
        """Establish/Verify authentication to the external system."""
        # Simple simulated auth check
        self.is_connected = bool(self.api_key)
        return self.is_connected

    @abstractmethod
    def fetch_data(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Fetch observational metrics/configuration from the system."""
        pass

    @abstractmethod
    def send_action(self, endpoint: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        """Mutate state in the remote system."""
        pass


# --- Implementations ---

class GitHubActionsConnector(Connector):
    def fetch_data(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("GitHub API token is missing or invalid.")
        return {"status": "success", "workflows": [f"{endpoint}_123", f"{endpoint}_124"]}

    def send_action(self, endpoint: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("GitHub API token is missing or invalid.")
        return {"status": "workflow_dispatched", "run_id": 9999}


class GitLabConnector(Connector):
    def fetch_data(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("GitLab API token is missing or invalid.")
        return {"pipeline_status": "passed"}

    def send_action(self, endpoint: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("GitLab API token is missing or invalid.")
        return {"action": "pipeline_triggered", "job_id": 8888}


class JenkinsConnector(Connector):
    def fetch_data(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Jenkins API token is missing or invalid.")
        return {"build_result": "SUCCESS", "duration": 4500}

    def send_action(self, endpoint: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Jenkins API token is missing or invalid.")
        return {"queue_id": 7777}


class DatadogConnector(Connector):
    def fetch_data(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Datadog API key is missing or invalid.")
        return {"series": [{"pointlist": [[time.time(), 0.015]]}]}

    def send_action(self, endpoint: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Datadog API key is missing or invalid.")
        return {"status": "event_posted"}


class SlackConnector(Connector):
    def fetch_data(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Slack API token is missing or invalid.")
        return {"messages": [{"user": "U123", "text": "Approval required."}]}

    def send_action(self, endpoint: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("Slack API token is missing or invalid.")
        return {"ok": True, "message_ts": "12345.67890"}


# --- Registry ---

class ConnectorRegistry:
    """Manages low-level Connectors."""
    def __init__(self):
        self._connectors: Dict[str, Connector] = {}

    def register(self, connector: Connector):
        self._connectors[connector.name] = connector

    def get_connector(self, name: str) -> Optional[Connector]:
        return self._connectors.get(name)

    def list_connectors(self) -> list[str]:
        return list(self._connectors.keys())
