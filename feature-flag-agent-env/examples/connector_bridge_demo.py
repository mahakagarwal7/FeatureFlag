"""
examples/connector_bridge_demo.py

Demonstrates how the newly added Connector Framework can be dynamically wrapped 
inside existing Tool classes, preserving 100% backward compatibility with the RL Environment.
"""

from typing import Dict, Any

from feature_flag_env.tools.tool_interface import Tool, ToolMode, ToolCallRequest
from feature_flag_env.tools.tool_manager import ToolManager

# Import the new Connectors
from feature_flag_env.tools.connectors import GitHubActionsConnector, ConnectorRegistry


class GitHubConnectedTool(Tool):
    """
    Bridge Pattern: Wraps the Connector but extends the ORIGINAL Tool API.
    Does NOT replace Tool classes; inherits from them.
    """
    def __init__(self, connector: GitHubActionsConnector):
        super().__init__(
            name="github",
            mode=ToolMode.REAL,
            available_actions=["get_deployment_status", "trigger_rollback"]
        )
        self.connector = connector
        # Ensure networking is established
        self.connector.connect()

    def _execute(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Overrides the abstract Tool._execute to dispatch to the Connector.
        """
        if action_name == "get_deployment_status":
            return self.connector.fetch_data("workflows/deploy", params)
        elif action_name == "trigger_rollback":
            return self.connector.send_action("workflows/rollback/dispatches", params)
        
        return {"error": "unsupported action mapping"}


def main():
    print("--- Connector to Tool Bridge Demo ---")

    # 1. Initialize Low-level Connectors (System Admin Context)
    registry = ConnectorRegistry()
    gh_connector = GitHubActionsConnector(
        name="github_actions", 
        base_url="https://api.github.com",
        api_key="gh_token_9x8c7"
    )
    registry.register(gh_connector)

    # 2. Bridge to the RL Environment Tool API
    # The environment itself continues using `ToolManager` and expects `Tool` objects.
    tool_manager = ToolManager()
    
    gh_tool = GitHubConnectedTool(connector=gh_connector)
    tool_manager.register(gh_tool)

    print(f"Tool Registered: {gh_tool.name} (Wrapping Connector: {gh_connector.name})")

    # 3. Simulate Agent invocation using the classic Tool API
    print("\n[Agent Calling get_deployment_status]")
    req1 = ToolCallRequest(tool_name="github", action_name="get_deployment_status", params={"env": "production"})
    result = tool_manager.execute(req1)
    print(result.summary)
    print("Underlying Data:", dict(result).get("data", {}))

    print("\n[Agent Calling trigger_rollback]")
    req2 = ToolCallRequest(tool_name="github", action_name="trigger_rollback", params={"ref": "main"})
    result2 = tool_manager.execute(req2)
    print(result2.summary)
    print("Underlying Data:", dict(result2).get("data", {}))


if __name__ == "__main__":
    main()
