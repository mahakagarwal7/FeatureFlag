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
    python inference.py --agent hitl --episodes 5 --task task2 --rl-model models/dqn_task2.pth

Hackathon Requirement: Must run without errors and produce reproducible scores.
"""

import argparse
import os
import sys
import json
import re
from typing import List, Dict, Any
import statistics

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation
from feature_flag_env.tasks.graders import get_grader


def _hitl_decision_label(reason: str) -> str:
    text = (reason or "").lower()
    if "human-approved" in text:
        return "HUMAN_APPROVED"
    if "human selected baseline policy" in text:
        return "HUMAN_BASELINE"
    if "human rejected" in text:
        return "HUMAN_REJECTED"
    if "custom rollout target" in text:
        return "HUMAN_CUSTOM"
    if "requested episode skip" in text:
        return "HUMAN_SKIP"
    if "non-interactive mode; using baseline" in text:
        return "NONINT_BASELINE"
    if "auto-approved (non-interactive mode)" in text:
        return "NONINT_APPROVED"
    if "auto-approved" in text:
        return "AUTO_APPROVED"
    return "UNSPECIFIED"


def _extract_confidence(reason: str) -> str:
    if not reason:
        return "-"
    match = re.search(r"confidence\s*=\s*([0-9]*\.?[0-9]+)", reason)
    if not match:
        return "-"
    return f"{float(match.group(1)):.2f}"


def _print_hitl_audit_table(rows: List[Dict[str, str]]) -> None:
    if not rows:
        return
    print("\n🧾 HITL Decision Audit")
    print("-" * 72)
    print(f"{'Step':<6}{'Decision':<20}{'Action':<20}{'Target%':<10}{'Conf':<8}")
    print("-" * 72)
    for row in rows:
        print(
            f"{row['step']:<6}{row['decision']:<20}{row['action']:<20}"
            f"{row['target']:<10}{row['confidence']:<8}"
        )
    print("-" * 72)


def _parse_weight_string(weights_text: str) -> Dict[str, float] | None:
    if not weights_text:
        return None
    parsed: Dict[str, float] = {}
    for token in weights_text.split(","):
        part = token.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"Invalid weight token: {part}")
        name, value = part.split("=", 1)
        key = name.strip().lower()
        if key not in {"rl", "baseline", "llm"}:
            raise ValueError(f"Unknown agent in weight token: {key}")
        parsed[key] = float(value.strip())
    return parsed or None


def _print_ensemble_stats(agent) -> None:
    if not hasattr(agent, "get_stats"):
        return
    stats = agent.get_stats()
    print("\nEnsemble Stats:")
    print(f"   Total decisions: {stats['total_decisions']}")
    print(f"   Agreement rate: {stats['agreement_rate']:.1f}%")
    print(f"   RL wins: {stats['rl_wins']}")
    print(f"   Baseline wins: {stats['baseline_wins']}")
    print(f"   LLM wins: {stats['llm_wins']}")


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
            print("WARNING: GROQ_API_KEY is not set. Using the baseline agent instead.")
            self.use_baseline = True
        else:
            self.use_baseline = False
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
            except ImportError:
                print("WARNING: groq package is not installed. Using the baseline agent.")
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

    def __init__(self, use_server: bool = False, server_url: str = "https://friizy-featureflag.hf.space", task: str = "task1"):
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
def run_episode(
    agent,
    env_client,
    task: str = "task1",
    debug: bool = False,
    enable_hitl_audit: bool = False,
) -> Dict[str, Any]:
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
    hitl_audit_rows: List[Dict[str, str]] = []
    
    print(f"\nEpisode Started")
    print(f"   Feature: {obs.feature_name}")
    print(f"   Initial Rollout: {obs.current_rollout_percentage}%")
    print(f"   Initial Errors: {obs.error_rate*100:.2f}%")
    
    step_count = 0
    while not obs.done and step_count < 50:
        if debug:
            state_done = env_client.env.state().done if (not env_client.use_server and env_client.env is not None) else None
            print(f"   [DEBUG] Loop start: step_count={step_count}, obs.done={obs.done}, state.done={state_done}")

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

        if enable_hitl_audit:
            hitl_audit_rows.append(
                {
                    "step": str(step_count + 1),
                    "decision": _hitl_decision_label(action.reason),
                    "action": action.action_type,
                    "target": f"{action.target_percentage:.1f}",
                    "confidence": _extract_confidence(action.reason),
                }
            )
        
        # Print step summary
        print(f"   Step {step_count + 1}: {action.action_type} -> {action.target_percentage}%")
        print(f"      Reward: {reward:+.2f} | Errors: {obs.error_rate*100:.2f}% | Health: {obs.system_health_score:.2f}")
        if debug:
            print(f"      [DEBUG] done={done}, info.done_reason={info.get('done_reason', '')}")
        
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
    
    print(f"\nEpisode Complete")
    print(f"   Steps: {step_count}")
    print(f"   Total Reward: {total_reward:+.2f}")
    print(f"   Final Rollout: {obs.current_rollout_percentage}%")
    print(f"   Final Errors: {obs.error_rate*100:.2f}%")
    print(f"   Task Score: {score:.3f}")

    if enable_hitl_audit:
        _print_hitl_audit_table(hitl_audit_rows)
    
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
        choices=["baseline", "llm", "hybrid", "rl", "hitl", "ensemble"],
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
        default="task3",
        choices=["task1", "task2", "task3"],
        help="Task to evaluate on"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run direct environment instead of cloud server"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print step-level done diagnostics"
    )
    parser.add_argument(
        "--server-url",
        type=str,
        default="https://friizy-featureflag.hf.space",
        help="Server URL if using HTTP"
    )
    parser.add_argument(
        "--rl-model",
        type=str,
        default=None,
        help="Path to RL model checkpoint for inference (optional)"
    )
    parser.add_argument(
        "--rl-train-mode",
        action="store_true",
        help="Run RL agent in training/exploration mode during inference"
    )
    parser.add_argument(
        "--hitl-threshold",
        type=float,
        default=0.75,
        help="Confidence threshold for auto-approval in HITL mode (0.0-1.0)"
    )
    parser.add_argument(
        "--hitl-noninteractive-action",
        type=str,
        default="baseline",
        choices=["baseline", "approve"],
        help="Fallback behavior when HITL runs without interactive stdin"
    )
    parser.add_argument(
        "--hitl-no-prompt",
        action="store_true",
        help="Disable human prompts and force non-interactive HITL behavior"
    )
    parser.add_argument(
        "--ensemble-strategy",
        type=str,
        default="weighted",
        choices=["weighted", "rl_with_safety", "majority", "confidence"],
        help="Voting strategy for ensemble mode"
    )
    parser.add_argument(
        "--ensemble-weights",
        type=str,
        default="",
        help="Optional weights format: rl=0.5,baseline=0.3,llm=0.2"
    )
    
    args = parser.parse_args()

    # Expose task context for simple rule-based policies that do not receive task explicitly.
    os.environ["FF_ACTIVE_TASK"] = args.task
    
    print("=" * 60)
    print("FEATURE FLAG AGENT - INFERENCE")
    print("=" * 60)
    print(f"   Agent: {args.agent}")
    print(f"   Episodes: {args.episodes}")
    print(f"   Task: {args.task}")
    print(f"   Use Server: {not args.local}")
    print("=" * 60)
    
    if args.agent == "rl":
        from agents.rl_agent import RLAgent
        if args.rl_train_mode:
            agent = RLAgent(task=args.task, model_path=args.rl_model, training=True)
            print("WARNING: RL is running in training mode (exploration enabled)")
        else:
            agent = RLAgent(
                task=args.task,
                model_path=args.rl_model,
                training=False,
                epsilon=0.0,
                epsilon_min=0.0,
            )
            agent.epsilon = 0.0
            print("RL is running in evaluation mode (deterministic policy)")
    elif args.agent == "hitl":
        from agents.human_in_loop_agent import HumanInLoopAgent

        agent = HumanInLoopAgent(
            task=args.task,
            model_path=args.rl_model,
            confidence_threshold=args.hitl_threshold,
            non_interactive_action=args.hitl_noninteractive_action,
            allow_human_prompt=not args.hitl_no_prompt,
        )
        prompt_state = "enabled" if not args.hitl_no_prompt else "disabled"
        print(
            "HITL mode enabled "
            f"(threshold={args.hitl_threshold:.2f}, prompts={prompt_state})"
        )
    elif args.agent == "ensemble":
        from agents.ensemble_agent import EnsembleAgent

        ensemble_weights = _parse_weight_string(args.ensemble_weights)
        agent = EnsembleAgent(
            task=args.task,
            model_path=args.rl_model,
            strategy=args.ensemble_strategy,
            weights=ensemble_weights,
        )
        weights_view = args.ensemble_weights if args.ensemble_weights else "default"
        print("Using multi-agent ensemble")
        print(f"   Voting strategy: {args.ensemble_strategy}")
        print(f"   Agent weights: {weights_view}")
    else:
        from agents.factory import get_agent
        agent = get_agent(args.agent)

    print(f"Using {args.agent.upper()} agent")
    
    # Create environment client
    env_client = EnvironmentClient(
        use_server=not args.local,
        server_url=args.server_url,
        task=args.task
    )
    
    # Run episodes
    scores = []
    for i in range(args.episodes):
        print(f"\n{'=' * 60}")
        print(f"Episode {i + 1}/{args.episodes}")
        print("=" * 60)
        
        if args.agent == "hitl":
            result = run_episode(
                agent,
                env_client,
                task=args.task,
                debug=args.debug,
                enable_hitl_audit=True,
            )
        else:
            result = run_episode(agent, env_client, task=args.task, debug=args.debug)
        scores.append(result["score"])

        if hasattr(agent, "decay_epsilon"):
            agent.decay_epsilon()

        if hasattr(agent, "reset"):
            agent.reset()
            
    # Summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"   Episodes: {args.episodes}")
    print(f"   Average Score: {sum(scores) / len(scores):.3f}")
    print(f"   Min Score: {min(scores):.3f}")
    print(f"   Max Score: {max(scores):.3f}")
    score_std = statistics.pstdev(scores) if len(scores) > 1 else 0.0
    print(f"   Score Std Dev: {score_std:.4f}")
    if max(scores) == min(scores) and args.agent == "rl" and not args.rl_train_mode:
        print("   Note: Min=Max is expected for deterministic RL when policy is stable.")
    if args.agent == "ensemble":
        _print_ensemble_stats(agent)
    print("=" * 60)
    
    return {
        "average_score": sum(scores) / len(scores),
        "min_score": min(scores),
        "max_score": max(scores),
        "episodes": args.episodes
    }


if __name__ == "__main__":
    main()