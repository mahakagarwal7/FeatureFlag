"""
inference.py

Baseline Inference Script for FeatureFlag-Agent-Env

This script demonstrates how to interact with the environment
using a simple rule-based agent. It's required for hackathon submission.

Usage:
    python inference.py --agent baseline --episodes 5
    python inference.py --agent llm --episodes 5
    python inference.py --agent hybrid --episodes 5
    python inference.py --agent rl --episodes 5

Hackathon Requirement: Must run without errors and produce reproducible scores.
"""

import argparse
import os
import sys
import json
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation
from feature_flag_env.tasks.graders import get_grader


# =============================================================================
# BASELINE AGENT (Rule-Based)
# =============================================================================
class BaselineAgent:
    """
    Simple rule-based agent for baseline comparison.
    
    Rules:
    - If errors < 3%: Increase rollout by 15%
    - If errors 3-7%: Maintain current rollout
    - If errors > 7%: Decrease rollout by 20%
    - If errors > 15%: Rollback to 0%
    """
    
    def decide(self, observation: FeatureFlagObservation, history: List) -> FeatureFlagAction:
        """Decide action based on current observation"""
        
        error_rate = observation.error_rate * 100  # Convert to percentage
        current_rollout = observation.current_rollout_percentage
        
        if error_rate > 15:
            # Emergency rollback
            action_type = "ROLLBACK"
            target = 0.0
            reason = f"Critical error rate ({error_rate:.1f}%) - emergency rollback"
        elif error_rate > 7:
            # Decrease rollout
            target = max(0.0, current_rollout - 20)
            action_type = "DECREASE_ROLLOUT"
            reason = f"High error rate ({error_rate:.1f}%) - decreasing rollout"
        elif error_rate > 3:
            # Maintain
            target = current_rollout
            action_type = "MAINTAIN"
            reason = f"Moderate error rate ({error_rate:.1f}%) - maintaining"
        else:
            # Increase rollout
            target = min(100.0, current_rollout + 15)
            action_type = "INCREASE_ROLLOUT"
            reason = f"Low error rate ({error_rate:.1f}%) - increasing rollout"
        
        return FeatureFlagAction(
            action_type=action_type,
            target_percentage=target,
            reason=reason
        )


# =============================================================================
# LLM AGENT (Groq)
# =============================================================================
class LLMAgent:
    """
    LLM-powered agent using Groq API.
    
    Generates reasoning + action via language model.
    """
    
    def __init__(self, model: str = "llama-3.1-8b-instant"):
        self.model = model
        self.api_key = os.getenv("GROQ_API_KEY")
        
        if not self.api_key:
            print("⚠️  WARNING: GROQ_API_KEY not set. Using baseline agent instead.")
            self.use_baseline = True
        else:
            self.use_baseline = False
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
            except ImportError:
                print("⚠️  WARNING: groq package not installed. Using baseline agent.")
                self.use_baseline = True
    
    def _build_prompt(self, obs: FeatureFlagObservation, history: List) -> str:
        """Build prompt for LLM"""
        return f"""
You are an AI agent controlling feature rollouts for a SaaS platform.

GOAL: Maximize feature adoption and revenue while keeping:
- Error rate < 5%
- Latency < 200ms
- System health > 0.7

CURRENT STATE:
- Feature: {obs.feature_name}
- Rollout: {obs.current_rollout_percentage:.1f}%
- Error Rate: {obs.error_rate*100:.2f}%
- Latency: {obs.latency_p99_ms:.1f}ms
- Adoption: {obs.user_adoption_rate*100:.1f}%
- Revenue: ${obs.revenue_impact:.2f}
- Health: {obs.system_health_score:.2f}
- Step: {obs.time_step}

AVAILABLE ACTIONS:
- INCREASE_ROLLOUT: Increase deployment percentage
- DECREASE_ROLLOUT: Decrease deployment percentage
- MAINTAIN: Keep current percentage
- HALT_ROLLOUT: Pause rollout temporarily
- FULL_ROLLOUT: Deploy to 100% immediately
- ROLLBACK: Emergency revert to 0%

Respond with JSON only:
{{
    "action_type": "...",
    "target_percentage": X,
    "reason": "..."
}}
"""
    
    def decide(self, observation: FeatureFlagObservation, history: List) -> FeatureFlagAction:
        """Decide action using LLM"""
        
        # Fallback to baseline if Groq not available
        if self.use_baseline:
            baseline = BaselineAgent()
            return baseline.decide(observation, history)
        
        try:
            # Build prompt
            prompt = self._build_prompt(observation, history)
            
            # Call Groq API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a feature flag rollout agent. Output JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            # Parse response
            content = response.choices[0].message.content
            data = json.loads(content)
            
            return FeatureFlagAction(
                action_type=data["action_type"],
                target_percentage=data["target_percentage"],
                reason=data.get("reason", "")
            )
            
        except Exception as e:
            print(f"⚠️  LLM error: {e}. Using baseline agent.")
            baseline = BaselineAgent()
            return baseline.decide(observation, history)


# =============================================================================
# HYBRID AGENT (LLM + Safety Constraints)
# =============================================================================
class HybridAgent:
    """
    Hybrid agent: LLM decides, baseline validates safety.
    
    Best of both worlds: LLM reasoning + rule-based safety.
    """
    
    def __init__(self):
        self.llm = LLMAgent()
        self.safety = BaselineAgent()
    
    def decide(self, observation: FeatureFlagObservation, history: List) -> FeatureFlagAction:
        """Decide action with safety validation"""
        
        # LLM proposes action
        proposed = self.llm.decide(observation, history)
        
        # Safety check: Never increase if errors > 10%
        if proposed.action_type == "INCREASE_ROLLOUT" and observation.error_rate > 0.10:
            # Override with safe action
            safe = self.safety.decide(observation, history)
            safe.reason = f"LLM overridden for safety. Original: {proposed.reason}"
            return safe
        
        return proposed


# =============================================================================
# ENVIRONMENT CLIENT
# =============================================================================
class EnvironmentClient:
    """
    Simple client to interact with the environment.
    
    Can connect to local server or use environment directly.
    """

    def __init__(self, use_server: bool = False, server_url: str = "http://localhost:8000", task: str = "task1"):
        self.use_server = use_server
        self.server_url = server_url
        self.env = None
        self.task = task

        if not use_server:
            # Use task-specific direct environment when possible
            if task == "task1":
                from feature_flag_env.tasks.task1_safe_rollout import make_task1_environment
                self.env = make_task1_environment()
            elif task == "task2":
                from feature_flag_env.tasks.task2_risk_aware import make_task2_environment
                self.env = make_task2_environment()
            elif task == "task3":
                from feature_flag_env.tasks.task3_multi_objective import make_task3_environment
                self.env = make_task3_environment()
            else:
                from feature_flag_env.server.feature_flag_environment import FeatureFlagEnvironment
                self.env = FeatureFlagEnvironment(scenario_config={"task_name": task})
    
    def reset(self) -> FeatureFlagObservation:
        """Reset environment"""
        if self.use_server:
            import httpx
            response = httpx.post(f"{self.server_url}/reset")
            data = response.json()
            return FeatureFlagObservation(**data["observation"])
        else:
            return self.env.reset()
    
    def step(self, action: FeatureFlagAction) -> tuple:
        """Execute action"""
        if self.use_server:
            import httpx
            response = httpx.post(
                f"{self.server_url}/step",
                json={
                    "action_type": action.action_type,
                    "target_percentage": action.target_percentage,
                    "reason": action.reason
                }
            )
            data = response.json()
            obs = FeatureFlagObservation(**data["observation"])
            return obs, data["reward"], data["done"], data["info"]
        else:
            response = self.env.step(action)
            return response.observation, response.reward, response.done, response.info
    
    def get_trajectory(self) -> List[Dict]:
        """Get current episode trajectory"""
        if self.use_server:
            import httpx
            response = httpx.get(f"{self.server_url}/state")
            return response.json()
        else:
            return self.env.state().model_dump()


# =============================================================================
# MAIN RUNNER
# =============================================================================
def run_episode(agent, env_client, task: str = "task1") -> Dict[str, Any]:
    """
    Run one episode and return results.
    
    Args:
        agent: Agent instance (Baseline, LLM, or Hybrid)
        env_client: EnvironmentClient instance
        task: Task name for grading
        
    Returns:
        Dictionary with episode results
    """
    # Reset environment
    obs = env_client.reset()
    
    # Track trajectory for grading
    trajectory = []
    total_reward = 0.0
    history = []
    
    print(f"\n🎬 Episode Started")
    print(f"   Feature: {obs.feature_name}")
    print(f"   Initial Rollout: {obs.current_rollout_percentage}%")
    print(f"   Initial Errors: {obs.error_rate*100:.2f}%")
    
    step_count = 0
    while not obs.done and step_count < 50:
        # Agent decides action
        action = agent.decide(obs, history)
        
        # Execute action
        obs, reward, done, info = env_client.step(action)
        
        # Record step
        trajectory.append({
            "observation": obs,
            "action": action,
            "reward": reward
        })
        history.append({"obs": obs, "action": action, "reward": reward})
        total_reward += reward
        
        # Print step summary
        print(f"   ⏩ Step {step_count + 1}: {action.action_type} → {action.target_percentage}%")
        print(f"      Reward: {reward:+.2f} | Errors: {obs.error_rate*100:.2f}% | Health: {obs.system_health_score:.2f}")
        
        step_count += 1
        
        if done:
            break
    
    # Final agent episode callback (optional)
    if hasattr(agent, "on_episode_end"):
        try:
            agent.on_episode_end(obs)
        except Exception:
            pass

    # Grade trajectory
    grader = get_grader(task)
    score = grader.grade(trajectory)
    
    print(f"\n📊 Episode Complete")
    print(f"   Steps: {step_count}")
    print(f"   Total Reward: {total_reward:+.2f}")
    print(f"   Final Rollout: {obs.current_rollout_percentage}%")
    print(f"   Final Errors: {obs.error_rate*100:.2f}%")
    print(f"   Task Score: {score:.3f}")
    
    return {
        "steps": step_count,
        "total_reward": total_reward,
        "final_rollout": obs.current_rollout_percentage,
        "final_error_rate": obs.error_rate,
        "score": score,
        "trajectory": trajectory
    }


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Feature Flag Agent Inference")
    parser.add_argument(
        "--agent",
        type=str,
        default="baseline",
        choices=["baseline", "llm", "hybrid", "rl"],
        help="Agent type to use"
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=5,
        help="Number of episodes to run"
    )
    parser.add_argument(
        "--task",
        type=str,
        default="task1",
        choices=["task1", "task2", "task3"],
        help="Task to evaluate on"
    )
    parser.add_argument(
        "--use-server",
        action="store_true",
        help="Use HTTP server instead of direct environment"
    )
    parser.add_argument(
        "--server-url",
        type=str,
        default="http://localhost:8000",
        help="Server URL if using HTTP"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 FEATURE FLAG AGENT - BASELINE INFERENCE")
    print("=" * 60)
    print(f"   Agent: {args.agent}")
    print(f"   Episodes: {args.episodes}")
    print(f"   Task: {args.task}")
    print(f"   Use Server: {args.use_server}")
    print("=" * 60)
    
    if args.agent == "rl":
        from agents.rl_agent import RLAgent
        agent = RLAgent(task=args.task)
    else:
        from agents.factory import get_agent
        agent = get_agent(args.agent)

    print(f"✅ Using {args.agent.upper()} Agent")
    
    # Create environment client
    env_client = EnvironmentClient(
        use_server=args.use_server,
        server_url=args.server_url,
        task=args.task
    )
    
    # Run episodes
    scores = []
    for i in range(args.episodes):
        print(f"\n{'=' * 60}")
        print(f"📍 Episode {i + 1}/{args.episodes}")
        print("=" * 60)
        
        result = run_episode(agent, env_client, task=args.task)
        scores.append(result["score"])

        if hasattr(agent, "decay_epsilon"):
            agent.decay_epsilon()

        if hasattr(agent, "reset"):
            agent.reset()
            
    # Summary
    print("\n" + "=" * 60)
    print("📊 FINAL SUMMARY")
    print("=" * 60)
    print(f"   Episodes: {args.episodes}")
    print(f"   Average Score: {sum(scores) / len(scores):.3f}")
    print(f"   Min Score: {min(scores):.3f}")
    print(f"   Max Score: {max(scores):.3f}")
    print("=" * 60)
    
    return {
        "average_score": sum(scores) / len(scores),
        "min_score": min(scores),
        "max_score": max(scores),
        "episodes": args.episodes
    }


if __name__ == "__main__":
    main()