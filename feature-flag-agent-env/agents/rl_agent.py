import os
import pickle
import random
from collections import defaultdict

import numpy as np
from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation


class RLAgent:
    def __init__(self, task: str = "task1"):
        self.task = task
        self.action_size = 5

        self.gamma = 0.95
        self.lr = 0.1
        self.epsilon = 0.8
        self.epsilon_decay = 0.995
        self.epsilon_min = 0.02

        self.last_state = None
        self.last_action = None

        local_table = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "q_table.pkl")
        )
        root_table = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "q_table.pkl")
        )
        self.q_table_file = local_table if os.path.exists(local_table) else root_table
        self.q_table = defaultdict(lambda: np.zeros(self.action_size, dtype=np.float32))
        self._load_q_table()

    def _load_q_table(self):
        if os.path.exists(self.q_table_file):
            try:
                with open(self.q_table_file, "rb") as handle:
                    data = pickle.load(handle)

                if isinstance(data, dict):
                    sample_key = next(iter(data), None)
                    sample_value = data[sample_key] if sample_key is not None else None

                    if (
                        sample_key is not None
                        and isinstance(sample_key, tuple)
                        and len(sample_key) == 2
                        and isinstance(sample_value, float)
                    ):
                        legacy_q = defaultdict(lambda: np.zeros(self.action_size, dtype=np.float32))
                        for (state_key, action), q_value in data.items():
                            legacy_q[state_key][action] = q_value
                        self.q_table = legacy_q
                    else:
                        self.q_table = defaultdict(
                            lambda: np.zeros(self.action_size, dtype=np.float32),
                            data,
                        )
                else:
                    self.q_table = defaultdict(lambda: np.zeros(self.action_size, dtype=np.float32))
            except Exception:
                self.q_table = defaultdict(lambda: np.zeros(self.action_size, dtype=np.float32))

    def _save_q_table(self):
        try:
            with open(self.q_table_file, "wb") as handle:
                pickle.dump(self.q_table, handle, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            pass

    def _discretize_value(self, value: float, min_val: float, max_val: float, step: float) -> int:
        idx = int(round((value - min_val) / step))
        max_idx = int(round((max_val - min_val) / step))
        return max(0, min(max_idx, idx))

    def _state_key(self, obs: FeatureFlagObservation):
        return (
            self._discretize_value(obs.current_rollout_percentage, 0.0, 100.0, 10.0),
            self._discretize_value(obs.error_rate, 0.0, 0.25, 0.05),
            self._discretize_value(obs.latency_p99_ms, 0.0, 500.0, 50.0),
            self._discretize_value(obs.user_adoption_rate, 0.0, 1.0, 0.1),
            self._discretize_value(obs.system_health_score, 0.0, 1.0, 0.1),
        )

    def _choose_action(self, state_key):
        if random.random() < self.epsilon:
            return random.randrange(self.action_size)
        return int(np.argmax(self.q_table[state_key]))

    def _action_to_env(self, action_id: int, obs: FeatureFlagObservation) -> FeatureFlagAction:
        current = obs.current_rollout_percentage

        if action_id == 0:
            target = current + 10.0
            if 20.0 <= current < 25.0:
                target = 25.0
            return FeatureFlagAction(
                action_type="INCREASE_ROLLOUT",
                target_percentage=min(100.0, target),
                reason="RL decision"
            )

        if action_id == 1:
            return FeatureFlagAction(
                action_type="FULL_ROLLOUT",
                target_percentage=100.0,
                reason="RL decision"
            )

        if action_id == 2:
            target = current - 10.0
            if 25.0 < current <= 30.0:
                target = 25.0
            return FeatureFlagAction(
                action_type="DECREASE_ROLLOUT",
                target_percentage=max(0.0, target),
                reason="RL decision"
            )

        if action_id == 3:
            return FeatureFlagAction(
                action_type="MAINTAIN",
                target_percentage=current,
                reason="RL decision"
            )

        return FeatureFlagAction(
            action_type="ROLLBACK",
            target_percentage=0.0,
            reason="RL decision"
        )

    def _update_q_value(self, state_key, action, reward, next_state_key, done):
        current_q = self.q_table[state_key][action]
        next_max = 0.0 if done else np.max(self.q_table[next_state_key])
        target = reward + self.gamma * next_max
        self.q_table[state_key][action] += self.lr * (target - current_q)

    def decide(self, observation: FeatureFlagObservation, history):
        state_key = self._state_key(observation)

        if self.last_state is not None and self.last_action is not None:
            reward = observation.reward if observation.reward is not None else 0.0
            self._update_q_value(self.last_state, self.last_action, reward, state_key, False)

        action_id = self._choose_action(state_key)
        self.last_state = state_key
        self.last_action = action_id

        return self._action_to_env(action_id, observation)

    def on_episode_end(self, terminal_observation: FeatureFlagObservation):
        if self.last_state is None or self.last_action is None:
            return

        terminal_state_key = self._state_key(terminal_observation)
        reward = terminal_observation.reward if terminal_observation.reward is not None else 0.0
        self._update_q_value(self.last_state, self.last_action, reward, terminal_state_key, True)
        self.last_state = None
        self.last_action = None
        self._save_q_table()
