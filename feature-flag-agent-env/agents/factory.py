from agents.baseline_agent import BaselineAgent
from agents.llm_agent import LLMAgent
from agents.hybrid_agent import HybridAgent
from agents.rl_agent import RLAgent


def get_agent(name: str):
    if name == "baseline":
        return BaselineAgent()
    elif name == "llm":
        return LLMAgent()
    elif name == "hybrid":
        return HybridAgent()
    elif name == "rl":
        return RLAgent()
    else:
        raise ValueError(f"Unknown agent: {name}")