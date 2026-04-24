"""
feature_flag_env/tools/datadog_integration.py

Datadog Integration for Feature Flag Agents using official datadog-api-client

Capabilities:
- Get real-time exact error rate metrics
- Get latency metrics (p99)
- Get active monitor/alert status for the deployment service

Install: pip install datadog-api-client

Usage:
    client = DatadogClient()
    auth_response = client.authenticate()
    
    error_rate = client.get_error_rate(service_name="payment-service")
    latency = client.get_latency(service_name="payment-service")
    alerts = client.get_active_alerts(tags=["service:payment-service"])
"""

import os
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from .base_tools import ExternalToolsInterface, ToolResponse, ToolStatus

class DatadogClient(ExternalToolsInterface):
    """
    Datadog integration for fetching real-time metrics and alerts.
    
    Requires Datadog API Key and APP Key.
    Ensure DD_SITE, DD_API_KEY, DD_APP_KEY are exposed in environment.
    """
    
    def __init__(self):
        super().__init__("datadog")
        
        if load_dotenv is not None:
            env_candidates = [
                Path.cwd() / ".env",
                Path(__file__).resolve().parents[2] / ".env",
                Path(__file__).resolve().parents[3] / ".env",
            ]
            for env_path in env_candidates:
                if env_path.exists():
                    load_dotenv(dotenv_path=env_path)
                    
        self.api_key = os.getenv("DD_API_KEY")
        self.app_key = os.getenv("DD_APP_KEY")
        self.site = os.getenv("DD_SITE", "datadoghq.com")
        
    def authenticate(self) -> ToolResponse:
        """Verify Authentication via Datadog validate API."""
        try:
            if not self.api_key or not self.app_key:
                error = "Datadog API key (DD_API_KEY) or APP key (DD_APP_KEY) not found in environment."
                self.status = ToolStatus.ERROR
                self._record_call(False, error)
                return ToolResponse(success=False, error=error)
                
            try:
                from datadog_api_client import ApiClient, Configuration
                from datadog_api_client.v1.api.authentication_api import AuthenticationApi
            except ImportError:
                error = "datadog-api-client not installed. Run: pip install datadog-api-client"
                self.status = ToolStatus.ERROR
                self._record_call(False, error)
                return ToolResponse(success=False, error=error)
            
            configuration = Configuration()
            # The client automatically picks up DD_API_KEY and DD_APP_KEY from env
            # but we can set it explicitly just in case
            configuration.api_key["apiKeyAuth"] = self.api_key
            configuration.api_key["appKeyAuth"] = self.app_key
            configuration.server_variables["site"] = self.site
            
            with ApiClient(configuration) as api_client:
                auth_api = AuthenticationApi(api_client)
                auth_res = auth_api.validate()
                
            self.status = ToolStatus.CONNECTED
            self._record_call(True)
            return ToolResponse(
                success=True,
                data={"valid": auth_res.valid, "site": self.site},
                metadata={"message": "Successfully authenticated with Datadog"}
            )
            
        except Exception as e:
            error = f"Datadog authentication failed: {str(e)}"
            self.status = ToolStatus.ERROR
            self._record_call(False, error)
            return ToolResponse(success=False, error=error)

    def get_status(self) -> ToolStatus:
        return self.status

    def _query_metric(self, query: str, window_minutes: int = 5) -> ToolResponse:
        """Internal helper to fetch metric."""
        try:
            if self.status != ToolStatus.CONNECTED:
                return ToolResponse(success=False, error="Not authenticated.")
                
            from datadog_api_client import ApiClient, Configuration
            from datadog_api_client.v1.api.metrics_api import MetricsApi
            
            to_time = int(time.time())
            from_time = to_time - (window_minutes * 60)
            
            configuration = Configuration()
            configuration.api_key["apiKeyAuth"] = self.api_key
            configuration.api_key["appKeyAuth"] = self.app_key
            configuration.server_variables["site"] = self.site

            with ApiClient(configuration) as api_client:
                api = MetricsApi(api_client)
                response = api.query_metrics(from_time, to_time, query)
                
            self._record_call(True)
            
            # Extract latest point
            latest_value = None
            if response.series and len(response.series) > 0:
                points = response.series[0].pointlist
                if points and len(points) > 0:
                    # points are usually [timestamp, value]
                    latest_value = float(points[-1][1])

            return ToolResponse(
                success=True,
                data={
                    "query": query,
                    "latest_value": latest_value,
                    "series_count": len(response.series) if response.series else 0
                },
                metadata={"timestamp": datetime.utcnow().isoformat()}
            )
        except Exception as e:
            error = f"Failed to query metric '{query}': {str(e)}"
            self._record_call(False, error)
            return ToolResponse(success=False, error=error)

    def get_error_rate(self, service_name: str, window_minutes: int = 5) -> ToolResponse:
        """
        Get the percentage of errors over total requests.
        Assuming metrics `trace.express.request.errors` and `trace.express.request.hits`
        Modify the query based on your actual APM setup.
        """
        # Example generic APM query for error rate percentage
        query = f"sum:trace.express.request.errors{{env:production,service:{service_name}}}.as_rate() / sum:trace.express.request.hits{{env:production,service:{service_name}}}.as_rate() * 100"
        return self._query_metric(query, window_minutes)

    def get_latency(self, service_name: str, window_minutes: int = 5) -> ToolResponse:
        """
        Get p99 latency in ms.
        Assuming metric `trace.express.request.duration.by.service.99p`
        """
        query = f"avg:trace.express.request.duration.by.service.99p{{env:production,service:{service_name}}}"
        return self._query_metric(query, window_minutes)

    def get_active_alerts(self, tags: List[str]) -> ToolResponse:
        """
        Get active monitors (Alerts) matching specific tags.
        """
        try:
            if self.status != ToolStatus.CONNECTED:
                return ToolResponse(success=False, error="Not authenticated.")
                
            from datadog_api_client import ApiClient, Configuration
            from datadog_api_client.v1.api.monitors_api import MonitorsApi
            
            configuration = Configuration()
            configuration.api_key["apiKeyAuth"] = self.api_key
            configuration.api_key["appKeyAuth"] = self.app_key
            configuration.server_variables["site"] = self.site
            
            # comma separated tags for API query
            tags_str = ",".join(tags)
            
            with ApiClient(configuration) as api_client:
                api = MonitorsApi(api_client)
                # group_states: Alert or Warn
                monitors = api.list_monitors(tags=tags_str, group_states="Alert")
                
            # Filter to monitors actually in Alert state
            active_alerts = []
            for m in monitors:
                if m.overall_state and m.overall_state.lower() in ['alert', 'warn']:
                    active_alerts.append({
                        "id": m.id,
                        "name": m.name,
                        "state": m.overall_state,
                        "priority": m.priority,
                        "tags": m.tags
                    })
                    
            self._record_call(True)
            return ToolResponse(
                success=True,
                data={"active_alerts": active_alerts, "total_alerts": len(active_alerts)},
                metadata={"timestamp": datetime.utcnow().isoformat()}
            )

        except Exception as e:
            error = f"Failed to get active alerts: {str(e)}"
            self._record_call(False, error)
            return ToolResponse(success=False, error=error)
