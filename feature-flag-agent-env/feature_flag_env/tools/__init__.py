"""
feature_flag_env/tools/

External tool integrations for agents to interact with real DevOps systems.

Supported tools:
- GitHub: Deployment status, PR creation, CI/CD pipeline info
- (Future) Slack: Notifications
- (Future) PagerDuty: Incident management
- (Future) Datadog: Monitoring
"""

from .github_integration import GitHubClient
from .datadog_integration import DatadogClient
from .slack_integration import SlackClient
from .base_tools import ExternalToolsInterface

__all__ = ["GitHubClient", "DatadogClient", "SlackClient", "ExternalToolsInterface"]
