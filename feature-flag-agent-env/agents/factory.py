from agents.baseline_agent import BaselineAgent
from agents.llm_agent import LLMAgent
from agents.hybrid_agent import HybridAgent


def get_agent(name: str, **kwargs):
    if name == "baseline":
        return BaselineAgent()
    elif name == "llm":
        return LLMAgent()
    elif name == "hybrid":
        return HybridAgent()
    elif name == "master":
        from agents.master_agent import MasterAgent
        return MasterAgent(**kwargs)
    elif name == "rl":
        from agents.rl_agent import RLAgent
        return RLAgent(**kwargs)
    elif name in {"hitl", "human_in_loop"}:
        from agents.human_in_loop_agent import HumanInLoopAgent
        return HumanInLoopAgent(**kwargs)
    elif name == "ensemble":
        from agents.ensemble_agent import EnsembleAgent
        return EnsembleAgent(**kwargs)
    else:
        raise ValueError(f"Unknown agent: {name}")