import os
import sys

from dotenv import load_dotenv

# Load .env explicitly
load_dotenv()

from langfuse import Langfuse
from feature_flag_env.models import FeatureFlagObservation
from agents.llm_agent import LLMAgent

def test_langfuse():
    print("Testing Langfuse Integration...")
    print(f"Host: {os.getenv('LANGFUSE_HOST')}")
    print(f"Public Key: {os.getenv('LANGFUSE_PUBLIC_KEY')}")
    
    # Init Langfuse to verify auth
    try:
        langfuse = Langfuse()
        print("Langfuse client initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize Langfuse: {e}")
        return

    print("=== Testing OpenAI ===")
    os.environ["LLM_PROVIDER"] = "openai"
    agent_openai = LLMAgent()
    
    obs = FeatureFlagObservation(
        current_rollout_percentage=50.0,
        error_rate=0.0,
        latency_p99_ms=100.0,
        user_adoption_rate=0.5,
        revenue_impact=100.0,
        system_health_score=0.99,
        active_users=1000,
        feature_name="TestFeature",
        time_step=1,
        reward=0.0,
        done=False,
    )

    print("Calling OpenAI agent.decide() to trigger Langfuse @observe...")
    action = agent_openai.decide(obs, history=[])
    print(f"OpenAI Agent decided action: {action.action_type} to {action.target_percentage}%")
    
    print("\n=== Testing Groq ===")
    os.environ["LLM_PROVIDER"] = "groq"
    agent_groq = LLMAgent()
    
    print("Calling Groq agent.decide() to trigger Langfuse @observe...")
    action2 = agent_groq.decide(obs, history=[])
    print(f"Groq Agent decided action: {action2.action_type} to {action2.target_percentage}%")
    
    # Flush langfuse events
    langfuse.flush()
    
    print("\nLangfuse events flushed. Check your dashboard!")

if __name__ == "__main__":
    test_langfuse()
