"""
examples/github_integration_demo.py

Demonstrates GitHub integration with Feature Flag Agents.

This example shows:
1. Initializing GitHub client
2. Checking deployment status
3. Creating PRs based on agent decisions
4. Monitoring CI/CD pipelines

Usage:
    python examples/github_integration_demo.py --owner your-org --repo your-repo

Prerequisites:
    1. Set GitHub token: export GITHUB_TOKEN=ghp_xxxxx
    2. Update repo info in .env or pass via CLI
"""

import argparse
import os
import json
from typing import Optional
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feature_flag_env.tools.github_integration import GitHubClient
from feature_flag_env.models import FeatureFlagObservation, FeatureFlagAction


class GitHubAwareAgent:
    """
    Example agent that uses GitHub integration to make decisions.
    """
    
    def __init__(self, github_client: GitHubClient):
        self.github_client = github_client
        self.deployment_checks = []
        self.prs_created = []
    
    def decide_with_github_context(
        self,
        observation: FeatureFlagObservation,
        feature_branch: str = "feature/rollout",
        target_branch: str = "main",
    ) -> dict:
        """
        Make rollout decision using both environment state and GitHub context.
        
        Returns:
            {
                "action": FeatureFlagAction,
                "github_context": {...},
                "reasoning": "..."
            }
        """
        
        # Step 1: Check deployment status
        print("\n🔍 Checking deployment status...")
        deploy_status = self.github_client.get_deployment_status(
            environment="production"
        )
        self.deployment_checks.append(deploy_status)
        
        # Step 2: Check CI/CD pipeline
        print("🔍 Checking CI/CD pipeline status...")
        pipeline_status = self.github_client.get_cicd_pipeline_status()
        
        # Step 3: Make decision
        decision_data = self._make_decision(
            observation,
            deploy_status,
            pipeline_status,
        )
        
        # Step 4: Create PR if conditions met
        if decision_data["should_create_pr"]:
            print(f"📝 Creating PR for {decision_data['target_rollout']}% rollout...")
            pr_response = self.github_client.create_rollout_pr(
                feature_branch=feature_branch,
                target_branch=target_branch,
                rollout_percentage=decision_data["target_rollout"],
                labels=["rollout", "automated"],
            )
            
            if pr_response.success:
                print(f"✅ PR created: {pr_response.data['pr_url']}")
                self.prs_created.append(pr_response)
            else:
                print(f"❌ PR creation failed: {pr_response.error}")
        
        return {
            "action": decision_data["action"],
            "github_context": {
                "deployment_status": deploy_status.data,
                "pipeline_status": pipeline_status.data,
            },
            "reasoning": decision_data["reasoning"],
            "pr_created": decision_data["should_create_pr"],
        }
    
    def _make_decision(
        self,
        observation: FeatureFlagObservation,
        deploy_status,
        pipeline_status,
    ) -> dict:
        """Internal decision logic"""
        
        error_rate = observation.error_rate
        latency = observation.latency_p99_ms
        current_rollout = observation.current_rollout_percentage
        
        # Check if deployment is healthy
        deployment_healthy = (
            deploy_status.success and
            deploy_status.data and
            len(deploy_status.data["deployments"]) > 0 and
            deploy_status.data["deployments"][0]["status"] == "success"
        )
        
        # Check if pipeline is passing
        pipeline_passing = (
            pipeline_status.success and
            pipeline_status.data and
            pipeline_status.data["summary"]["success_rate"] > 80.0
        )
        
        # Make decision
        reasoning = []
        action_type = "MAINTAIN"
        target_rollout = current_rollout
        should_create_pr = False
        
        if not deployment_healthy:
            action_type = "ROLLBACK"
            target_rollout = 0
            reasoning.append("⚠️ Last deployment has issues, rolling back")
        
        elif not pipeline_passing:
            action_type = "HALT_ROLLOUT"
            target_rollout = current_rollout
            reasoning.append("⚠️ CI/CD pipeline failing, halting rollout")
        
        elif error_rate < 0.02 and latency < 150:
            # Green light for rollout
            if current_rollout < 50:
                action_type = "INCREASE_ROLLOUT"
                target_rollout = min(current_rollout + 15, 50)
                should_create_pr = True
                reasoning.append("✅ Healthy metrics, increasing rollout")
                reasoning.append(f"✅ Deployment healthy, pipeline passing")
            elif current_rollout < 80:
                action_type = "INCREASE_ROLLOUT"
                target_rollout = min(current_rollout + 10, 80)
                should_create_pr = True
                reasoning.append("✅ Gradual increase to 80%")
            else:
                action_type = "FULL_ROLLOUT"
                target_rollout = 100
                should_create_pr = True
                reasoning.append("🎉 All systems go for full rollout")
        
        elif error_rate < 0.05:
            action_type = "MAINTAIN"
            target_rollout = current_rollout
            reasoning.append("⚠️ Moderate error rate, holding steady")
        
        else:
            action_type = "DECREASE_ROLLOUT"
            target_rollout = max(current_rollout - 10, 0)
            reasoning.append("❌ Error rate rising, decreasing rollout")
        
        action = FeatureFlagAction(
            action_type=action_type,
            target_percentage=target_rollout,
            reason="; ".join(reasoning),
        )
        
        return {
            "action": action,
            "target_rollout": target_rollout,
            "should_create_pr": should_create_pr,
            "reasoning": "\n".join(reasoning),
        }


def run_demo(
    owner: str,
    repo: str,
    token: Optional[str] = None,
    episodes: int = 3,
):
    """Run the demo"""
    
    print(f"🚀 GitHub Integration Demo")
    print(f"Repository: {owner}/{repo}")
    print("=" * 60)
    
    # Step 1: Initialize GitHub client
    print("\n📌 Step 1: Initialize GitHub Client")
    print("-" * 60)
    
    github_client = GitHubClient(
        token=token,
        owner=owner,
        repo_name=repo,
    )
    
    # Step 2: Authenticate
    print("🔐 Authenticating with GitHub...")
    auth_response = github_client.authenticate()
    
    if not auth_response.success:
        print(f"❌ Authentication failed: {auth_response.error}")
        print("\n💡 Make sure to:")
        print("   1. Set GITHUB_TOKEN environment variable")
        print("   2. Use --token flag or set in .env")
        print("   3. Token needs: repo + workflow permissions")
        return
    
    print("✅ Authenticated successfully!")
    print(f"   Owner: {auth_response.data['owner']}")
    print(f"   Repo: {auth_response.data['repo']}")
    
    # Step 3: Check initial deployment status
    print("\n📌 Step 2: Check Initial Deployment Status")
    print("-" * 60)
    
    deploy_info = github_client.get_deployment_status(environment="production", limit=3)
    
    if deploy_info.success and deploy_info.data["deployments"]:
        for deploy in deploy_info.data["deployments"]:
            print(f"\n  Deployment ID: {deploy['id']}")
            print(f"  Environment: {deploy['environment']}")
            print(f"  Status: {deploy['status']}")
            print(f"  Branch: {deploy['ref']}")
            print(f"  Commit: {deploy['sha']}")
            print(f"  Creator: {deploy['creator']}")
    else:
        print("   No deployments found (first time or private repo)")
    
    # Step 4: Check CI/CD pipeline
    print("\n📌 Step 3: Check CI/CD Pipeline Status")
    print("-" * 60)
    
    pipeline_info = github_client.get_cicd_pipeline_status(branch="main", limit=5)
    
    if pipeline_info.success and pipeline_info.data["recent_runs"]:
        summary = pipeline_info.data["summary"]
        print(f"\n  Recent Workflow Runs:")
        print(f"  Total Checked: {summary['total_checked']}")
        print(f"  ✅ Successful: {summary['successful']}")
        print(f"  ❌ Failed: {summary['failed']}")
        print(f"  🔄 In Progress: {summary['in_progress']}")
        print(f"  Success Rate: {summary['success_rate']:.1f}%")
        
        if pipeline_info.data["recent_runs"]:
            print(f"\n  Recent Runs:")
            for run in pipeline_info.data["recent_runs"][:3]:
                print(f"    - {run['workflow_name']}: {run['conclusion'] or run['status']}")
    else:
        print("   No workflow runs found")
    
    # Step 5: Simulate agent decisions
    print("\n📌 Step 4: Simulate Agent Decisions with GitHub Context")
    print("-" * 60)
    
    agent = GitHubAwareAgent(github_client)
    
    # Simulate episodes
    for episode in range(1, episodes + 1):
        print(f"\n🎬 Episode {episode}/{episodes}")
        print("-" * 40)
        
        # Mock observation (in real use, comes from environment)
        observation = FeatureFlagObservation(
            current_rollout_percentage=25.0 + (episode - 1) * 15,
            error_rate=0.01 + (episode - 1) * 0.005,
            latency_p99_ms=100 + (episode - 1) * 20,
            user_adoption_rate=0.3 + (episode - 1) * 0.1,
            revenue_impact=150 + (episode - 1) * 50,
            system_health_score=0.9 - (episode - 1) * 0.05,
            active_users=2500 + (episode - 1) * 500,
            feature_name="test-feature",
            time_step=episode * 10,
        )
        
        # Get decision
        decision = agent.decide_with_github_context(
            observation,
            feature_branch="feature/test-rollout",
            target_branch="main",
        )
        
        print(f"\n📊 State:")
        print(f"   Rollout: {observation.current_rollout_percentage:.1f}%")
        print(f"   Error Rate: {observation.error_rate:.4f}")
        print(f"   Latency: {observation.latency_p99_ms:.1f}ms")
        
        print(f"\n🤖 Agent Decision:")
        print(f"   Action: {decision['action'].action_type}")
        print(f"   Target: {decision['action'].target_percentage:.1f}%")
        print(f"   Reasoning:")
        for line in decision['reasoning'].split("\n"):
            print(f"     {line}")
    
    # Step 6: Summary
    print("\n📌 Step 5: Summary")
    print("-" * 60)
    
    metrics = github_client.get_metrics()
    print(f"\n📊 GitHub Client Metrics:")
    print(f"   Total API Calls: {metrics['total_calls']}")
    print(f"   Errors: {metrics['error_count']}")
    print(f"   Error Rate: {metrics['error_rate']:.1%}")
    print(f"   Status: {metrics['status']}")
    
    if agent.prs_created:
        print(f"\n📝 PRs Created: {len(agent.prs_created)}")
        for pr in agent.prs_created:
            if pr.success:
                print(f"   - #{pr.data['pr_number']}: {pr.data['title']}")
                print(f"     URL: {pr.data['pr_url']}")
    else:
        print(f"\n📝 PRs Created: 0")
    
    print("\n✅ Demo complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="GitHub Integration Demo for Feature Flag Agents"
    )
    parser.add_argument("--owner", help="GitHub organization/user", default="microsoft")
    parser.add_argument("--repo", help="GitHub repository", default="vscode")
    parser.add_argument("--token", help="GitHub token (or set GITHUB_TOKEN env var)")
    parser.add_argument("--episodes", type=int, default=3, help="Number of episodes to simulate")
    
    args = parser.parse_args()
    
    run_demo(
        owner=args.owner,
        repo=args.repo,
        token=args.token,
        episodes=args.episodes,
    )