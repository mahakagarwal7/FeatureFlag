"""
examples/datadog_integration_demo.py

Demonstrates Datadog integration with Feature Flag Agents.

This example shows:
1. Initializing Datadog client
2. Checking real-time error rates
3. Checking latency
4. Checking for active monitors/alerts

Prerequisites:
    1. pip install datadog-api-client
    2. Set up Datadog tokens in the .env file

---
HOW TO GENERATE DATADOG API & APP KEYS:
1. Log in to your Datadog account.
2. Generating the API Key (DD_API_KEY):
   - Go to Organization Settings at the bottom left.
   - Click on "API Keys" under the "Access" section.
   - Click "New Key", give it a name like "FeatureFlagAgent", and copy the key.
3. Generating the APP Key (DD_APP_KEY):
   - In Organization Settings, click on "Application Keys" under the "Access" section.
   - Click "New Key", give it a name, and copy the key.
4. Add these to your `.env` file:
   DD_API_KEY=your_api_key_here
   DD_APP_KEY=your_app_key_here
   DD_SITE=datadoghq.com (Optional, defaults to datadoghq.com, use datadoghq.eu for EU etc.)
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feature_flag_env.tools.datadog_integration import DatadogClient
from feature_flag_env.models import FeatureFlagAction

class DatadogAwareAgent:
    def __init__(self, datadog_client: DatadogClient, service_name: str):
        self.client = datadog_client
        self.service_name = service_name
        
    def check_system_health(self):
        print("\n🔍 Checking active Datadog alerts...")
        alerts_response = self.client.get_active_alerts(tags=[f"service:{self.service_name}"])
        
        print(f"🔍 Checking error rate for '{self.service_name}'...")
        error_response = self.client.get_error_rate(service_name=self.service_name)
        
        print(f"🔍 Checking latency for '{self.service_name}'...")
        latency_response = self.client.get_latency(service_name=self.service_name)
        
        has_alerts = False
        error_rate = 0.0
        latency = 0.0
        
        if alerts_response.success and alerts_response.data["total_alerts"] > 0:
            print(f"⚠️  WARNING: {alerts_response.data['total_alerts']} active alert(s) found!")
            has_alerts = True
            for alert in alerts_response.data["active_alerts"]:
                print(f"   - {alert['name']} [{alert['state']}]")
        else:
            print("✅ No active alerts.")
            
        if error_response.success:
            error_rate = error_response.data.get("latest_value") or 0.0
            print(f"📊 Error Rate: {error_rate:.4f}%")
        else:
            print(f"⚠️  Failed to fetch error rate: {error_response.error}")
            
        if latency_response.success:
            latency = latency_response.data.get("latest_value") or 0.0
            print(f"⏱️  Latency (p99): {latency:.2f} ms")
        else:
            print(f"⚠️  Failed to fetch latency. Error: {latency_response.error}")
            
        # Decision Logic based on Datadog
        if has_alerts or error_rate > 5.0 or latency > 1000:
            print("\n❌ System health is poor. Decision: ROLLBACK")
        elif error_rate > 1.0 or latency > 500:
            print("\n⚠️  System health is degraded. Decision: HALT_ROLLOUT")
        else:
            print("\n✅ System health is good. Decision: INCREASE_ROLLOUT")


def run_demo():
    print("🚀 Datadog Integration Demo")
    print("=" * 60)
    
    print("\n📌 Step 1: Initialize Datadog Client")
    print("-" * 60)
    
    client = DatadogClient()
    
    print("🔐 Authenticating with Datadog...")
    auth_response = client.authenticate()
    
    if not auth_response.success:
        print(f"❌ Authentication failed: {auth_response.error}")
        print("\n💡 Please generate keys and add them to your .env file:")
        print("1. Go to Datadog > Org Settings > API Keys")
        print("2. Go to Datadog > Org Settings > Application Keys")
        print("3. Add DD_API_KEY and DD_APP_KEY to .env file.")
        return
        
    print(f"✅ Authenticated successfully! (Site: {auth_response.data['site']})")
    
    print("\n📌 Step 2: Agent Health Checks")
    print("-" * 60)
    # the service_name depends on your APM setup. We use 'payment-service' as a dummy.
    agent = DatadogAwareAgent(client, service_name="payment-service")
    agent.check_system_health()
    
    print("\n📌 Step 3: API Usage Summary")
    print("-" * 60)
    metrics = client.get_metrics()
    print(f"Total API Calls: {metrics['total_calls']}")
    print(f"Errors: {metrics['error_count']}")
    
    print("\n✅ Demo complete!")

if __name__ == "__main__":
    run_demo()