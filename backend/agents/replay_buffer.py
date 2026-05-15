"""Experience Replay Buffer for DQN Training."""

import random
from collections import deque
from dataclasses import dataclass
from typing import Tuple, Dict, Any, List

import numpy as np


@dataclass
class Transition:
    """A single transition tuple: (state, action, reward, next_state, done)."""
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool


class ReplayBuffer:
    """
    Experience replay buffer for storing and sampling transitions.
    
    Used to break correlations between training samples by storing transitions
    and sampling mini-batches randomly for training. This improves DQN stability.
    
    Args:
        capacity: Maximum number of transitions to store (default 10,000)
    """
    
    def __init__(self, capacity: int = 10000):
        """Initialize replay buffer with fixed capacity."""
        self.buffer: deque = deque(maxlen=capacity)
        self.capacity = capacity
        self.rewards_history: List[float] = []
    
    def push(
        self, 
        state: np.ndarray, 
        action: int, 
        reward: float, 
        next_state: np.ndarray, 
        done: bool
    ) -> None:
        """
        Store a transition in the replay buffer.
        
        Args:
            state: Current state (9-dim normalized vector)
            action: Action taken (int 0-5)
            reward: Reward received
            next_state: Resulting next state
            done: Whether episode terminated
        """
        transition = Transition(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=done,
        )
        self.buffer.append(transition)
        self.rewards_history.append(reward)
        
        # Keep rewards history to reasonable size
        if len(self.rewards_history) > self.capacity:
            self.rewards_history.pop(0)
    
    def sample(self, batch_size: int = 64) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Sample a random batch of transitions.
        
        Args:
            batch_size: Number of transitions to sample
            
        Returns:
            Tuple of (states, actions, rewards, next_states, dones) as numpy arrays
        """
        sample_size = min(len(self.buffer), batch_size)
        if sample_size <= 0:
            raise ValueError("Cannot sample from an empty replay buffer")

        batch = random.sample(self.buffer, sample_size)
        
        states = np.array([t.state for t in batch], dtype=np.float32)
        actions = np.array([t.action for t in batch], dtype=np.int64)
        rewards = np.array([t.reward for t in batch], dtype=np.float32)
        next_states = np.array([t.next_state for t in batch], dtype=np.float32)
        dones = np.array([float(t.done) for t in batch], dtype=np.float32)
        
        return states, actions, rewards, next_states, dones
    
    def __len__(self) -> int:
        """Return current buffer size."""
        return len(self.buffer)
    
    def is_ready(self, batch_size: int = 64) -> bool:
        """Check if buffer has enough samples to train."""
        return len(self.buffer) >= batch_size
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the buffer.
        
        Returns:
            Dictionary with:
                - size: Current number of transitions
                - capacity: Maximum capacity
                - full: Whether buffer is at capacity
                - avg_reward: Average reward in buffer
                - min_reward: Minimum reward
                - max_reward: Maximum reward
                - std_reward: Standard deviation of rewards
        """
        if not self.rewards_history:
            return {
                'size': 0,
                'capacity': self.capacity,
                'full': False,
                'avg_reward': 0.0,
                'min_reward': 0.0,
                'max_reward': 0.0,
                'std_reward': 0.0,
            }
        
        rewards_array = np.array(self.rewards_history, dtype=np.float32)
        return {
            'size': len(self.buffer),
            'capacity': self.capacity,
            'full': len(self.buffer) == self.capacity,
            'avg_reward': float(np.mean(rewards_array)),
            'min_reward': float(np.min(rewards_array)),
            'max_reward': float(np.max(rewards_array)),
            'std_reward': float(np.std(rewards_array)),
        }
    
    def clear(self) -> None:
        """Clear the replay buffer (for starting fresh episodes)."""
        self.buffer.clear()
        self.rewards_history.clear()
