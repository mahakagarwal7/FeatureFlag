"""
examples/slack_integration_demo.py

Demonstrates Slack integration with Feature Flag Agents.

This example shows:
1. Initializing Slack client
2. Using the built-in rich Block Kit formatter to broadcast rollout decisions

Prerequisites:
    1. pip install slack_sdk
    2. Set up Slack bot token in the .env file

---
HOW TO GENERATE SLACK BOT TOKEN:
1. Go to https://api.slack.com/apps and log in.
2. Click "Create New App" -> "From scratch". Give it a name like "FeatureFlagAgent".
3. Under "Features" on the left, click "OAuth & Permissions".
4. Scroll down to "Scopes" -> "Bot Token Scopes" and click "Add an OAuth Scope".
5. Add the `chat:write` scope.
6. Scroll back up and click "Install to Workspace".
7. Copy the "Bot User OAuth Token" (starts with xoxb-).
8. Add this to your `.env` file:
   SLACK_BOT_TOKEN=xoxb-your-token-here

IMPORTANT: The bot must be added to the channel you want to post to.
Open Slack, go to the channel, type `@FeatureFlagAgent` and invite it.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feature_flag_env.tools.slack_integration import SlackClient

def run_demo():
    print("🚀 Slack Integration Demo")
    print("=" * 60)
    
    print("\n📌 Step 1: Initialize Slack Client")
    print("-" * 60)
    
    client = SlackClient()
    
    print("🔐 Authenticating with Slack...")
    auth_response = client.authenticate()
    
    if not auth_response.success:
        print(f"❌ Authentication failed: {auth_response.error}")
        print("\n💡 Please create a Slack App and get a bot token:")
        print("1. Go to https://api.slack.com/apps")
        print("2. Create an App, add 'chat:write' scope in OAuth & Permissions.")
        print("3. Install to Workspace and copy the Bot User OAuth Token.")
        print("4. Add SLACK_BOT_TOKEN=xoxb-... to .env file.")
        return
        
    print(f"✅ Authenticated successfully! (Bot name: {auth_response.data['user']})")
    
    print("\n📌 Step 2: Agent Post Simulation")
    print("-" * 60)
    
    channel = "#general"  # Replace with an actual test channel
    feature_name = "ui-v3-darkmode"
    
    print(f"🤖 Simulating agent decision for {feature_name}...")
    
    # Simulate the agent deciding to increase rollout based on good metrics
    action = "INCREASE_ROLLOUT"
    new_percentage = 25.0
    metrics = {
        "error_rate": "0.012% (Healthy)",
        "latency": 45.2
    }
    reasoning = "Latency and error rates are well below thresholds. Safely increasing population tier to 25%."
    
    print(f"📣 Broadcasting to Slack channel: {channel}")
    
    res = client.send_rollout_update(
        channel=channel,
        feature_name=feature_name,
        action=action,
        percentage=new_percentage,
        metrics=metrics,
        reasoning=reasoning
    )
    
    if res.success:
        print(f"✅ Message sent successfully! Check Slack.")
    else:
        print(f"⚠️ Failed to send message: {res.error}")
        if "not_in_channel" in str(res.error):
            print(f"💡 TIP: You MUST invite the bot to the channel in Slack first.")
            print(f"   Go to {channel} and type @{auth_response.data['user']} to add it.")
            
    print("\n✅ Demo complete!")

if __name__ == "__main__":
    run_demo()