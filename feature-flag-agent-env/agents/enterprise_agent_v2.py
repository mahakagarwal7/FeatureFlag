import os
import random
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from typing import List, Optional
from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation
from agents.replay_buffer import ReplayBuffer
from agents.rl_agent import RLAgent, DQN

class EnterpriseAgentV2(RLAgent):
    """
    Specialized 22-Dimensional RL Agent for Enterprise Rollouts.
    Includes Anomaly Detection, Benchmarking, and Pattern Risk context.
    """
    def __init__(self, *args, **kwargs):
        # Initialize with 22 dimensions instead of the default 19
        super().__init__(*args, **kwargs)
        self.state_dim = 22 
        
        # Re-initialize the networks with the new dimension
        self.policy_net = DQN(self.state_dim, self.action_dim).to(self.device)
        self.target_net = DQN(self.state_dim, self.action_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=kwargs.get('lr', 1e-3))

    def encode_state(self, obs: FeatureFlagObservation) -> np.ndarray:
        # Use the specialized 22-dimensional method we're adding to models.py
        encoded = obs.to_master_numpy()
        if self.state_safety_enabled:
            return self.validate_and_clip_state(encoded, source="enterprise_state")
        return encoded
