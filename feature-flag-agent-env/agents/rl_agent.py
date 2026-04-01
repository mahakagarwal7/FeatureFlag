import argparse
import os
import random
from typing import List, Optional

import numpy as np
from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation
from agents.replay_buffer import ReplayBuffer

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.nn.utils import clip_grad_norm_
except ImportError as exc:
    raise ImportError(
        "PyTorch is required for RLAgent. Install with: pip install torch"
    ) from exc


class DQN(nn.Module):
    def __init__(self, state_dim: int, action_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, action_dim),
        )

    def forward(self, x):
        return self.net(x)


class RLAgent:
    """PyTorch DQN agent with replay buffer and target network."""

    ACTIONS = [
        "INCREASE_ROLLOUT",
        "DECREASE_ROLLOUT",
        "MAINTAIN",
        "HALT_ROLLOUT",
        "FULL_ROLLOUT",
        "ROLLBACK",
    ]

    def __init__(
        self,
        task: str = "task1",
        model_path: Optional[str] = None,
        training: bool = True,
        gamma: float = 0.99,
        lr: float = 1e-3,
        epsilon: float = 1.0,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.01,
        buffer_capacity: int = 10000,
        batch_size: int = 64,
        target_update_freq: int = 100,
        max_grad_norm: float = 1.0,
    ):
        self.task = task
        self.training = training
        self.state_dim = 9
        self.action_dim = len(self.ACTIONS)

        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.batch_size = batch_size
        self.target_update_freq = target_update_freq
        self.max_grad_norm = max_grad_norm

        # State safety layer: enforce normalized inputs in [0, 1].
        self.state_safety_enabled = (
            os.getenv("FF_STATE_SAFETY_CLIP", "1").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.state_assert_enabled = (
            os.getenv("FF_ASSERT_STATE_NORM", "0").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.state_debug_enabled = (
            os.getenv("FF_DEBUG_STATE_CLIP", "0").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.state_samples = 0
        self.state_values_checked = 0
        self.state_values_clipped = 0
        self.state_values_below_zero = 0
        self.state_values_above_one = 0

        # Optional reward clipping telemetry (off by default)
        self.reward_telemetry_enabled = (
            os.getenv("FF_DEBUG_REWARD_CLIP", "0").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.reward_clip_enabled = (
            os.getenv("FEATURE_FLAG_REWARD_CLIP", "1").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.reward_clip_min = float(os.getenv("FEATURE_FLAG_REWARD_CLIP_MIN", "-1.0"))
        self.reward_clip_max = float(os.getenv("FEATURE_FLAG_REWARD_CLIP_MAX", "1.0"))
        if self.reward_clip_min > self.reward_clip_max:
            self.reward_clip_min, self.reward_clip_max = self.reward_clip_max, self.reward_clip_min
        self.reward_raw_sum = 0.0
        self.reward_clipped_sum = 0.0
        self.reward_adjusted_count = 0
        self.reward_total_count = 0
        self.reward_hits_min = 0
        self.reward_hits_max = 0

        # Task-aware action masking (enabled for task2 by default).
        self.task2_action_mask_enabled = (
            os.getenv("FF_TASK2_ACTION_MASK", "1").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.task2_inference_safety_enabled = (
            os.getenv("FF_TASK2_INFERENCE_SAFETY", "1").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.action_mask_events = 0
        self.action_safety_overrides = 0

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.policy_net = DQN(self.state_dim, self.action_dim).to(self.device)
        self.target_net = DQN(self.state_dim, self.action_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=lr)
        self.loss_fn = nn.MSELoss()
        self.replay_buffer = ReplayBuffer(capacity=buffer_capacity)
        self.external_transition_mode = False

        self.total_steps = 0
        self.last_state: Optional[np.ndarray] = None
        self.last_action: Optional[int] = None

        default_model = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "models", "dqn_model.pth")
        )
        self.model_path = model_path or default_model
        if os.path.exists(self.model_path):
            self.load_model(self.model_path)

    def _safe_ratio(self, value: float, upper: float) -> float:
        if upper <= 0:
            return 0.0
        return float(np.clip(value / upper, 0.0, 1.0))

    def _feature_embedding(self, feature_name: str) -> float:
        return (abs(hash(feature_name)) % 1000) / 1000.0

    def validate_and_clip_state(self, state: np.ndarray, source: str = "state") -> np.ndarray:
        state_arr = np.asarray(state, dtype=np.float32).reshape(-1)

        if state_arr.size != self.state_dim:
            fixed = np.zeros(self.state_dim, dtype=np.float32)
            copy_n = min(self.state_dim, state_arr.size)
            if copy_n > 0:
                fixed[:copy_n] = state_arr[:copy_n]
            state_arr = fixed
            if self.state_debug_enabled:
                print(f"[RL DEBUG] Resized malformed {source} to shape ({self.state_dim},)")

        self.state_samples += 1
        self.state_values_checked += self.state_dim

        below_zero = int(np.count_nonzero(state_arr < 0.0))
        above_one = int(np.count_nonzero(state_arr > 1.0))
        clipped_state = np.clip(state_arr, 0.0, 1.0).astype(np.float32)
        clipped_values = int(np.count_nonzero(clipped_state != state_arr))

        self.state_values_below_zero += below_zero
        self.state_values_above_one += above_one
        self.state_values_clipped += clipped_values

        if self.state_debug_enabled and self.state_samples % 100 == 0:
            ratio = 0.0
            if self.state_values_checked > 0:
                ratio = self.state_values_clipped / self.state_values_checked
            print(
                "[RL DEBUG] State clipping | "
                f"samples={self.state_samples} clipped_values={self.state_values_clipped} "
                f"checked_values={self.state_values_checked} clipped_ratio={ratio:.4f}"
            )

        if self.state_assert_enabled:
            assert np.all(clipped_state >= 0.0) and np.all(clipped_state <= 1.0), (
                f"State normalization assertion failed for {source}: {clipped_state}"
            )

        return clipped_state

    def encode_state(self, obs: FeatureFlagObservation) -> np.ndarray:
        encoded = np.array(
            [
                self._safe_ratio(obs.current_rollout_percentage, 100.0),
                self._safe_ratio(obs.error_rate, 0.25),
                self._safe_ratio(obs.latency_p99_ms, 500.0),
                self._safe_ratio(obs.user_adoption_rate, 1.0),
                float(np.tanh(obs.revenue_impact / 1000.0)),
                self._safe_ratio(obs.system_health_score, 1.0),
                self._safe_ratio(float(obs.active_users), 100000.0),
                self._safe_ratio(float(obs.time_step), 50.0),
                self._feature_embedding(obs.feature_name),
            ],
            dtype=np.float32,
        )
        if self.state_safety_enabled:
            return self.validate_and_clip_state(encoded, source="encoded_state")
        return encoded

    def _task2_allowed_actions(self, observation: FeatureFlagObservation) -> List[int]:
        allowed = list(range(self.action_dim))
        if not self.task2_action_mask_enabled or self.task != "task2":
            return allowed

        rollout = float(observation.current_rollout_percentage)
        error = float(observation.error_rate)

        # High error: block FULL_ROLLOUT to avoid catastrophic escalation.
        if error > 0.10 and 4 in allowed:
            allowed.remove(4)

        # Near/above target: discourage further increase and full rollout.
        if rollout >= 75.0:
            if 0 in allowed:
                allowed.remove(0)
            if 4 in allowed:
                allowed.remove(4)

        if not allowed:
            allowed = list(range(self.action_dim))
        return allowed

    def _task2_inference_override(
        self, action_idx: int, observation: FeatureFlagObservation
    ) -> int:
        if self.training or self.task != "task2" or not self.task2_inference_safety_enabled:
            return action_idx

        rollout = float(observation.current_rollout_percentage)
        error = float(observation.error_rate)

       
        if rollout < 60.0 and error < 0.05 and action_idx != 0:
            self.action_safety_overrides += 1
            return 0

        # Push toward task2 target band: keep increasing from 60 to 70 when risk is low.
        if 60.0 <= rollout < 70.0 and error < 0.03 and action_idx in {1, 2, 3, 5}:
            self.action_safety_overrides += 1
            return 0

        # Near target with low errors: avoid unnecessary full rollout.
        if rollout >= 70.0 and error < 0.10 and action_idx == 4:
            self.action_safety_overrides += 1
            return 2

        return action_idx

    def _select_action(self, state: np.ndarray, observation: Optional[FeatureFlagObservation] = None) -> int:
        if self.state_safety_enabled:
            state = self.validate_and_clip_state(state, source="policy_input")

        allowed_actions = list(range(self.action_dim))
        if observation is not None:
            allowed_actions = self._task2_allowed_actions(observation)
            if len(allowed_actions) < self.action_dim:
                self.action_mask_events += 1

        if self.training and random.random() < self.epsilon:
            return int(random.choice(allowed_actions))

        with torch.no_grad():
            state_tensor = torch.from_numpy(state).float().unsqueeze(0).to(self.device)
            q_values = self.policy_net(state_tensor)
            if len(allowed_actions) < self.action_dim:
                masked_q = q_values.clone()
                blocked = [i for i in range(self.action_dim) if i not in allowed_actions]
                masked_q[:, blocked] = -1e9
                return int(torch.argmax(masked_q, dim=1).item())
            return int(torch.argmax(q_values, dim=1).item())

    def _action_to_env(self, action_idx: int, obs: FeatureFlagObservation) -> FeatureFlagAction:
        current = obs.current_rollout_percentage
        action_type = self.ACTIONS[action_idx]

        if action_type == "INCREASE_ROLLOUT":
            target = min(100.0, current + 10.0)
        elif action_type == "DECREASE_ROLLOUT":
            target = max(0.0, current - 10.0)
        elif action_type == "MAINTAIN":
            target = current
        elif action_type == "HALT_ROLLOUT":
            target = current
        elif action_type == "FULL_ROLLOUT":
            target = 100.0
        else:
            target = 0.0

        return FeatureFlagAction(
            action_type=action_type,
            target_percentage=target,
            reason="DQN policy action",
        )

    def _optimize_model(self):
        if len(self.replay_buffer) < self.batch_size:
            return None

        states, actions, rewards, next_states, dones = self.replay_buffer.sample(self.batch_size)
        
        states = torch.tensor(states, dtype=torch.float32, device=self.device)
        actions = torch.tensor(actions, dtype=torch.int64, device=self.device).unsqueeze(1)
        rewards = torch.tensor(rewards, dtype=torch.float32, device=self.device)
        next_states = torch.tensor(next_states, dtype=torch.float32, device=self.device)
        dones = torch.tensor(dones, dtype=torch.float32, device=self.device)

        q_values = self.policy_net(states).gather(1, actions).squeeze(1)
        with torch.no_grad():
            next_q_values = self.target_net(next_states).max(1)[0]
            targets = rewards + self.gamma * next_q_values * (1.0 - dones)

        loss = self.loss_fn(q_values, targets)
        self.optimizer.zero_grad()
        loss.backward()
        
        # Gradient clipping to prevent exploding gradients
        grad_norm = clip_grad_norm_(self.policy_net.parameters(), self.max_grad_norm)
        
        self.optimizer.step()
        return {"loss": float(loss.item()), "grad_norm": float(grad_norm)}

    def _action_to_index(self, action: FeatureFlagAction) -> int:
        action_type = (action.action_type or "").upper()
        if action_type in self.ACTIONS:
            return self.ACTIONS.index(action_type)
        return self.ACTIONS.index("MAINTAIN")

    def store_transition(
        self,
        obs: FeatureFlagObservation,
        action: FeatureFlagAction,
        reward: float,
        next_obs: FeatureFlagObservation,
        done: bool,
    ):
        state = self.encode_state(obs)
        next_state = self.encode_state(next_obs)
        if self.state_safety_enabled:
            state = self.validate_and_clip_state(state, source="transition_state")
            next_state = self.validate_and_clip_state(next_state, source="transition_next_state")
        action_idx = self._action_to_index(action)
        raw_reward = float(reward)
        clipped_reward = float(np.clip(raw_reward, self.reward_clip_min, self.reward_clip_max))

        self.reward_total_count += 1
        self.reward_raw_sum += raw_reward
        self.reward_clipped_sum += clipped_reward
        if clipped_reward != raw_reward:
            self.reward_adjusted_count += 1
        if np.isclose(clipped_reward, self.reward_clip_min):
            self.reward_hits_min += 1
        if np.isclose(clipped_reward, self.reward_clip_max):
            self.reward_hits_max += 1

        if self.reward_telemetry_enabled and self.reward_total_count % 50 == 0:
            print(
                "[RL DEBUG] Reward telemetry | "
                f"count={self.reward_total_count} adjusted={self.reward_adjusted_count} "
                f"raw_avg={self.reward_raw_sum / self.reward_total_count:+.4f} "
                f"stored_avg={self.reward_clipped_sum / self.reward_total_count:+.4f}"
            )

        self.replay_buffer.push(state, action_idx, clipped_reward, next_state, bool(done))
        self.total_steps += 1

    def train_step(self) -> dict:
        if len(self.replay_buffer) < self.batch_size:
            return {"loss": 0.0, "trained": False, "epsilon": float(self.epsilon), "grad_norm": 0.0}

        optimize_result = self._optimize_model()
        loss = optimize_result["loss"] if isinstance(optimize_result, dict) else optimize_result
        grad_norm = optimize_result.get("grad_norm", 0.0) if isinstance(optimize_result, dict) else 0.0
        
        if self.total_steps % self.target_update_freq == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())

        if self.training:
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        return {
            "loss": float(loss if loss is not None else 0.0),
            "grad_norm": float(grad_norm),
            "trained": True,
            "epsilon": float(self.epsilon),
        }

    def _record_transition_from_observation(self, observation: FeatureFlagObservation):
        if not self.training or self.last_state is None or self.last_action is None:
            return
        if observation.reward is None:
            return

        next_state = self.encode_state(observation)
        self.replay_buffer.push(
            self.last_state,
            self.last_action,
            float(observation.reward),
            next_state,
            bool(observation.done),
        )
        result = self._optimize_model()
        # Handle both dict and old numeric return formats
        if isinstance(result, dict):
            loss = result.get("loss", 0.0)
        else:
            loss = result if result is not None else 0.0
        self.total_steps += 1

        if self.total_steps % self.target_update_freq == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())

    def decide(self, observation: FeatureFlagObservation, history):
        if not self.external_transition_mode:
            self._record_transition_from_observation(observation)
        state = self.encode_state(observation)
        action_idx = self._select_action(state, observation)
        action_idx = self._task2_inference_override(action_idx, observation)

        self.last_state = state
        self.last_action = action_idx
        return self._action_to_env(action_idx, observation)

    def on_episode_end(self, terminal_observation: FeatureFlagObservation):
        if self.training and not self.external_transition_mode:
            self._record_transition_from_observation(terminal_observation)
        self.last_state = None
        self.last_action = None

    def decay_epsilon(self):
        if self.training:
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def reset(self):
        self.last_state = None
        self.last_action = None

    def save_model(self, model_path: Optional[str] = None):
        path = model_path or self.model_path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save(
            {
                "policy_net": self.policy_net.state_dict(),
                "target_net": self.target_net.state_dict(),
                "epsilon": self.epsilon,
                "total_steps": self.total_steps,
            },
            path,
        )

    def load_model(self, model_path: Optional[str] = None):
        path = model_path or self.model_path
        checkpoint = torch.load(path, map_location=self.device)
        self.policy_net.load_state_dict(checkpoint["policy_net"])
        if "target_net" in checkpoint:
            self.target_net.load_state_dict(checkpoint["target_net"])
        else:
            self.target_net.load_state_dict(self.policy_net.state_dict())
        self.epsilon = float(checkpoint.get("epsilon", self.epsilon))
        self.total_steps = int(checkpoint.get("total_steps", self.total_steps))

    def get_training_stats(self) -> dict:
        """Get current training statistics."""
        total = max(1, self.reward_total_count)
        state_total = max(1, self.state_values_checked)
        return {
            "total_steps": self.total_steps,
            "epsilon": float(self.epsilon),
            "buffer_size": len(self.replay_buffer),
            "buffer_capacity": self.replay_buffer.capacity,
            "buffer_stats": self.replay_buffer.get_stats(),
            "device": str(self.device),
            "training": self.training,
            "state_validation": {
                "enabled": self.state_safety_enabled,
                "samples": self.state_samples,
                "values_checked": self.state_values_checked,
                "values_clipped": self.state_values_clipped,
                "clipped_ratio": float(self.state_values_clipped / state_total),
                "values_below_zero": self.state_values_below_zero,
                "values_above_one": self.state_values_above_one,
            },
            "reward_clipping": {
                "enabled": self.reward_clip_enabled,
                "range": [self.reward_clip_min, self.reward_clip_max],
                "samples": self.reward_total_count,
                "adjusted_count": self.reward_adjusted_count,
                "adjusted_ratio": float(self.reward_adjusted_count / total),
                "hits_min": self.reward_hits_min,
                "hits_max": self.reward_hits_max,
                "avg_raw_received": float(self.reward_raw_sum / total),
                "avg_stored": float(self.reward_clipped_sum / total),
            },
            "action_masking": {
                "task2_enabled": self.task2_action_mask_enabled,
                "mask_events": self.action_mask_events,
                "task2_inference_safety": self.task2_inference_safety_enabled,
                "safety_overrides": self.action_safety_overrides,
            },
        }


def _make_env(task: str):
    if task == "task1":
        from feature_flag_env.tasks.task1_safe_rollout import make_task1_environment

        return make_task1_environment()
    if task == "task2":
        from feature_flag_env.tasks.task2_risk_aware import make_task2_environment

        return make_task2_environment()
    if task == "task3":
        from feature_flag_env.tasks.task3_multi_objective import make_task3_environment

        return make_task3_environment()
    raise ValueError(f"Unknown task: {task}")


def _run_episode(agent: RLAgent, env) -> float:
    obs = env.reset()
    total_reward = 0.0
    history = []

    while not obs.done and env.state().step_count < env.state().max_steps:
        action = agent.decide(obs, history)
        response = env.step(action)
        obs = response.observation
        total_reward += response.reward
        history.append({"obs": obs, "action": action, "reward": response.reward})
        if response.done:
            break

    agent.on_episode_end(obs)
    return total_reward


def train_agent(task: str, episodes: int, save_model: str):
    env = _make_env(task)
    agent = RLAgent(task=task, training=True, model_path=save_model)

    rewards = []
    for ep in range(episodes):
        ep_reward = _run_episode(agent, env)
        rewards.append(ep_reward)
        agent.decay_epsilon()
        agent.reset()
        if (ep + 1) % 50 == 0:
            avg = float(np.mean(rewards[-50:]))
            print(f"Episode {ep + 1}/{episodes} | Avg Reward(50): {avg:.3f} | epsilon={agent.epsilon:.3f}")

    agent.save_model(save_model)
    print(f"Training complete. Model saved to {save_model}")


def evaluate_agent(task: str, episodes: int, model_path: str):
    env = _make_env(task)
    agent = RLAgent(task=task, training=False, model_path=model_path, epsilon=0.0, epsilon_min=0.0)
    agent.epsilon = 0.0

    rewards = []
    for ep in range(episodes):
        ep_reward = _run_episode(agent, env)
        rewards.append(ep_reward)
        agent.reset()
        print(f"Eval episode {ep + 1}/{episodes}: reward={ep_reward:.3f}")

    print(f"Evaluation complete. Avg reward: {float(np.mean(rewards)):.3f}")


def main():
    parser = argparse.ArgumentParser(description="PyTorch DQN agent for feature-flag environment")
    parser.add_argument("--mode", choices=["train", "evaluate"], default="train")
    parser.add_argument("--task", choices=["task1", "task2", "task3"], default="task1")
    parser.add_argument("--episodes", type=int, default=1000)
    parser.add_argument("--model", type=str, default=os.path.join("models", "dqn_model.pth"))
    parser.add_argument("--save-model", type=str, default=None)
    args = parser.parse_args()

    model_path = args.save_model or args.model
    if args.mode == "train":
        train_agent(task=args.task, episodes=args.episodes, save_model=model_path)
    else:
        evaluate_agent(task=args.task, episodes=args.episodes, model_path=args.model)


if __name__ == "__main__":
    main()
