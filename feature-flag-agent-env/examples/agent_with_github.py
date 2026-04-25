"""
examples/agent_with_github.py

Example: Integration with existing agent types
Shows how to add GitHub tools to:
- LLM Agent
- Baseline Agent  
- Hybrid Agent
- RL Agent

Usage:
    python examples/agent_with_github.py --agent llm --episodes 3
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feature_flag_env.models import FeatureFlagObservation, FeatureFlagAction
from feature_flag_env.tools.github_integration import GitHubClient
from feature_flag_env.server.feature_flag_environment import FeatureFlagEnvironment


# =============================================================================
# BASELINE AGENT WITH GITHUB
# =============================================================================

class GitHubAwareBaselineAgent:
    """
    Baseline agent enhanced with GitHub health checks.
    Falls back to conservative strategy if GitHub health is poor.
    """
    
    def __init__(self, github_client: GitHubClient):
        self.github = github_client
    
    def decide(self, observation: FeatureFlagObservation) -> FeatureFlagAction:
        error_rate = observation.error_rate * 100
        current_rollout = observation.current_rollout_percentage
        
        # Step 1: Check GitHub health
        deploy_status = self.github.get_deployment_status(limit=1)
        
        if not deploy_status.success:
            # GitHub unreachable, use conservative baseline
            return self._baseline_decision(observation)
        
        if deploy_status.data["deployments"]:
            latest_deploy = deploy_status.data["deployments"][0]
            if latest_deploy["status"] != "success":
                # Last deployment failed, halt
                return FeatureFlagAction(
                    action_type="HALT_ROLLOUT",
                    target_percentage=current_rollout,
                    reason=f"⚠️ Recent deployment failed: {latest_deploy['status']}"
                )
        
        # Step 2: Normal baseline logic
        return self._baseline_decision(observation)
    
    def _baseline_decision(self, observation: FeatureFlagObservation) -> FeatureFlagAction:
        """Standard baseline logic"""
        error_rate = observation.error_rate * 100
        current_rollout = observation.current_rollout_percentage
        
        if error_rate < 3:
            return FeatureFlagAction(
                action_type="INCREASE_ROLLOUT",
                target_percentage=min(current_rollout + 15, 100),
                reason=f"✅ Error rate {error_rate:.1f}% < 3%, increasing"
            )
        elif error_rate < 7:
            return FeatureFlagAction(
                action_type="MAINTAIN",
                target_percentage=current_rollout,
                reason=f"⚠️ Error rate {error_rate:.1f}% in range [3-7%], maintaining"
            )
        elif error_rate < 15:
            return FeatureFlagAction(
                action_type="DECREASE_ROLLOUT",
                target_percentage=max(current_rollout - 20, 0),
                reason=f"❌ Error rate {error_rate:.1f}% > 7%, decreasing"
            )
        else:
            return FeatureFlagAction(
                action_type="ROLLBACK",
                target_percentage=0,
                reason=f"🚨 Error rate {error_rate:.1f}% > 15%, rollback"
            )


# =============================================================================
# LLM AGENT WITH GITHUB CONTEXT
# =============================================================================

class GitHubAwareLLMAgent:
    """
    LLM agent that includes GitHub context in its reasoning.
    Uses deployment and pipeline status to inform decisions.
    """
    
    def __init__(self, github_client: GitHubClient):
        self.github = github_client
        self.api_calls = 0
    
    def decide(self, observation: FeatureFlagObservation) -> FeatureFlagAction:
        """Make decision considering GitHub context"""
        
        # Get GitHub context
        deploy_status = self.github.get_deployment_status(limit=3)
        pipeline_status = self.github.get_cicd_pipeline_status()
        
        self.api_calls += 2
        
        # Build reasoning
        reasoning = self._build_reasoning(
            observation,
            deploy_status,
            pipeline_status
        )
        
        # Simulate LLM decision based on reasoning
        action = self._simulate_llm_decision(observation, reasoning)
        
        return action
    
    def _build_reasoning(self, obs, deploy_status, pipeline_status):
        """Build structured reasoning"""
        
        reasoning = f"""
FEATURE ROLLOUT DECISION

Current State:
- Rollout: {obs.current_rollout_percentage:.1f}%
- Error Rate: {obs.error_rate:.4f} ({obs.error_rate*100:.2f}%)
- Latency: {obs.latency_p99_ms:.1f}ms
- Health Score: {obs.system_health_score:.2f}/1.0
- Adoption Rate: {obs.user_adoption_rate:.4f}

GitHub Deployment Status:
"""
        
        if deploy_status.success and deploy_status.data["deployments"]:
            latest = deploy_status.data["deployments"][0]
            reasoning += f"""
- Latest: {latest['status']} ({latest['ref']} @ {latest['sha']})
- Creator: {latest['creator']}
- Time: {latest['created_at']}
"""
        else:
            reasoning += "- Unable to fetch deployment status\n"
        
        reasoning += "\nGitHub Pipeline Status:\n"
        
        if pipeline_status.success:
            summary = pipeline_status.data["summary"]
            reasoning += f"""
- Total Runs: {summary['total_checked']}
- Success Rate: {summary['success_rate']:.1f}%
- Successful: {summary['successful']}/{summary['total_checked']}
- Failed: {summary['failed']}
- In Progress: {summary['in_progress']}
"""
        else:
            reasoning += "- Unable to fetch pipeline status\n"
        
        return reasoning
    
    def _simulate_llm_decision(self, obs, reasoning):
        """Simulate LLM decision logic"""
        
        # Analyze metrics
        error_acceptable = obs.error_rate < 0.05
        latency_acceptable = obs.latency_p99_ms < 200
        health_good = obs.system_health_score > 0.7
        
        if not (error_acceptable and latency_acceptable and health_good):
            return FeatureFlagAction(
                action_type="DECREASE_ROLLOUT",
                target_percentage=max(obs.current_rollout_percentage - 10, 0),
                reason=f"Metrics out of range. {reasoning}"
            )
        
        # Healthy - decide on rollout progression
        if obs.current_rollout_percentage < 30:
            target = min(obs.current_rollout_percentage + 20, 50)
            return FeatureFlagAction(
                action_type="INCREASE_ROLLOUT",
                target_percentage=target,
                reason=f"✅ Metrics healthy, ramping up to {target:.0f}%. {reasoning}"
            )
        elif obs.current_rollout_percentage < 70:
            target = min(obs.current_rollout_percentage + 15, 80)
            return FeatureFlagAction(
                action_type="INCREASE_ROLLOUT",
                target_percentage=target,
                reason=f"✅ Steady progress to {target:.0f}%. {reasoning}"
            )
        else:
            return FeatureFlagAction(
                action_type="FULL_ROLLOUT",
                target_percentage=100,
                reason=f"🎉 Ready for full rollout. {reasoning}"
            )


# =============================================================================
# HYBRID AGENT WITH GITHUB
# =============================================================================

class GitHubAwareHybridAgent:
    """
    Hybrid agent that uses GitHub status to choose between
    conservative (baseline) or aggressive (LLM) strategies.
    """
    
    def __init__(self, github_client: GitHubClient):
        self.github = github_client
        self.baseline = GitHubAwareBaselineAgent(github_client)
        self.llm = GitHubAwareLLMAgent(github_client)
    
    def decide(self, observation: FeatureFlagObservation) -> FeatureFlagAction:
        """
        Use GitHub health to decide strategy:
        - Unhealthy: Use conservative baseline
        - Healthy: Use aggressive LLM
        """
        
        # Check overall system health
        deploy_status = self.github.get_deployment_status(limit=1)
        pipeline_status = self.github.get_cicd_pipeline_status()
        
        is_system_healthy = self._check_system_health(deploy_status, pipeline_status)
        
        if is_system_healthy:
            # Use LLM for aggressive rollout
            action = self.llm.decide(observation)
            action.reason = f"🤖 LLM Strategy (System Healthy): {action.reason}"
            return action
        else:
            # Use baseline for conservative rollout
            action = self.baseline.decide(observation)
            action.reason = f"📋 Baseline Strategy (System Issues): {action.reason}"
            return action
    
    def _check_system_health(self, deploy_status, pipeline_status):
        """Check if system is healthy enough for aggressive rollout"""
        
        # Check deployments
        if deploy_status.success and deploy_status.data["deployments"]:
            latest = deploy_status.data["deployments"][0]
            if latest["status"] != "success":
                return False
        
        # Check pipeline
        if pipeline_status.success:
            success_rate = pipeline_status.data["summary"]["success_rate"]
            if success_rate < 70.0:
                return False
        
        return True


# =============================================================================
# MAIN DEMO
# =============================================================================

def run_agents_with_github(episodes: int = 3):
    """Run all agent types with GitHub integration"""
    
    print("🚀 Feature Flag Agents with GitHub Integration")
    print("=" * 70)
    
    # Initialize GitHub client
    print("\n📌 Initializing GitHub Client")
    print("-" * 70)
    
    github = GitHubClient(
        owner="microsoft",  # You can change this
        repo_name="vscode"  # You can change this
    )
    
    auth = github.authenticate()
    if not auth.success:
        print(f"❌ GitHub authentication failed: {auth.error}")
        print("\n💡 Setup GitHub token:")
        print("   1. Go to https://github.com/settings/tokens")
        print("   2. Create token with 'repo' + 'workflow' scopes")
        print("   3. Add to .env: GITHUB_TOKEN=ghp_xxxxx")
        return
    
    print(f"✅ Authenticated with: {auth.data['owner']}/{auth.data['repo']}")
    
    # Initialize environment
    print("\n📌 Initializing Environment")
    print("-" * 70)
    env = FeatureFlagEnvironment()
    
    # Initialize agents
    print("\n📌 Creating Agents")
    print("-" * 70)
    
    baseline_agent = GitHubAwareBaselineAgent(github)
    llm_agent = GitHubAwareLLMAgent(github)
    hybrid_agent = GitHubAwareHybridAgent(github)
    
    agents = {
        "baseline": baseline_agent,
        "llm": llm_agent,
        "hybrid": hybrid_agent,
    }
    
    print(f"✅ Created {len(agents)} agents with GitHub awareness")
    
    # Run episodes
    print("\n📌 Running Episodes")
    print("-" * 70)
    
    for agent_name, agent in agents.items():
        print(f"\n🎬 {agent_name.upper()} AGENT")
        
        for episode in range(episodes):
            obs = env.reset()
            
            # Get action
            action = agent.decide(obs)
            
            # Step environment
            step_response = env.step(action)
            
            print(f"\n  Episode {episode + 1}:")
            print(f"    State: Rollout {obs.current_rollout_percentage:.0f}%, "
                  f"Errors {obs.error_rate*100:.2f}%")
            print(f"    Action: {action.action_type} → {action.target_percentage:.0f}%")
            print(f"    Score: {step_response.episode_reward:.3f}")
    
    # Summary
    print("\n📌 Summary")
    print("-" * 70)
    
    metrics = github.get_metrics()
    print(f"\n📊 GitHub Client Metrics:")
    print(f"   Total API Calls: {metrics['total_calls']}")
    print(f"   Errors: {metrics['error_count']}")
    print(f"   Error Rate: {metrics['error_rate']:.1%}")
    
    print(f"\n📊 Agent Usage:")
    print(f"   Baseline LLM Calls: {llm_agent.api_calls}")
    
    print("\n✅ Demo complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Feature Flag Agents with GitHub Integration"
    )
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--owner", default="microsoft")
    parser.add_argument("--repo", default="vscode")
    
    args = parser.parse_args()
    
    run_agents_with_github(episodes=args.episodes)