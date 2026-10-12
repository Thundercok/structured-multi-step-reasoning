"""
meta_controller.agent — Masked Double-DQN Meta-Controller for Dynamic LLM Reasoning.
Learns a policy pi(a | s) that balances accuracy vs. token cost & latency
by dynamically routing queries across reasoning strategies (CoT, SC, ToT, ReAct, PAL, Escalate, Stop).
"""

from __future__ import annotations

import logging
import random
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

logger = logging.getLogger(__name__)


class MaskedQNetwork(nn.Module):
    """
    Q-Network estimating action-values Q(s, a).
    Applies action masking during forward inference to guarantee zero invalid actions.
    """

    def __init__(self, state_dim: int, action_dim: int = 7, hidden_dim: int = 128) -> None:
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim),
        )

    def forward(self, state: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        q_values = self.fc(state)
        if mask is not None:
            # Set invalid actions to large negative number (-1e9)
            neg_inf = torch.tensor(-1e9, device=q_values.device, dtype=q_values.dtype)
            q_values = torch.where(mask, q_values, neg_inf)
        return q_values


@dataclass
class Transition:
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool
    next_mask: np.ndarray


class ReplayBuffer:
    """Experience replay buffer for off-policy Double DQN training."""

    def __init__(self, capacity: int = 10000) -> None:
        self.buffer: deque[Transition] = deque(maxlen=capacity)

    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
        next_mask: np.ndarray,
    ) -> None:
        self.buffer.append(Transition(state, action, reward, next_state, done, next_mask))

    def sample(self, batch_size: int) -> Transition:
        transitions = random.sample(self.buffer, batch_size)
        return Transition(
            state=np.array([t.state for t in transitions], dtype=np.float32),
            action=np.array([t.action for t in transitions], dtype=np.int64),
            reward=np.array([t.reward for t in transitions], dtype=np.float32),
            next_state=np.array([t.next_state for t in transitions], dtype=np.float32),
            done=np.array([t.done for t in transitions], dtype=np.bool_),
            next_mask=np.array([t.next_mask for t in transitions], dtype=np.bool_),
        )

    def __len__(self) -> int:
        return len(self.buffer)


class MaskedDoubleDQNAgent:
    """
    Masked Double Deep Q-Network (DDQN) Agent for Dynamic Reasoning Meta-Control.
    Prevents overestimation bias and respects Gymnasium action masks at all decision steps.
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int = 7,
        hidden_dim: int = 128,
        lr: float = 1e-3,
        gamma: float = 0.95,
        target_update_freq: int = 50,
        buffer_capacity: int = 10000,
        device: Optional[str] = None,
    ) -> None:
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.target_update_freq = target_update_freq

        if device is None:
            if torch.backends.mps.is_available():
                self.device = torch.device("mps")
            elif torch.cuda.is_available():
                self.device = torch.device("cuda")
            else:
                self.device = torch.device("cpu")
        else:
            self.device = torch.device(device)

        self.q_online = MaskedQNetwork(state_dim, action_dim, hidden_dim).to(self.device)
        self.q_target = MaskedQNetwork(state_dim, action_dim, hidden_dim).to(self.device)
        self.q_target.load_state_dict(self.q_online.state_dict())
        self.q_target.eval()

        self.optimizer = optim.Adam(self.q_online.parameters(), lr=lr)
        self.loss_fn = nn.SmoothL1Loss()  # Huber loss for stable Q-learning
        self.replay_buffer = ReplayBuffer(buffer_capacity)

        self.train_steps = 0

    def select_action(
        self,
        state: np.ndarray,
        action_mask: np.ndarray,
        epsilon: float = 0.0,
    ) -> int:
        """
        Epsilon-greedy action selection respecting the boolean action_mask.
        """
        valid_actions = np.where(action_mask)[0]
        if len(valid_actions) == 0:
            # Fallback if somehow all are masked
            return int(np.random.randint(self.action_dim))

        if random.random() < epsilon:
            return int(random.choice(valid_actions))

        with torch.no_grad():
            s_tensor = torch.tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0)
            m_tensor = torch.tensor(action_mask, dtype=torch.bool, device=self.device).unsqueeze(0)
            q_values = self.q_online(s_tensor, m_tensor)
            best_action = int(torch.argmax(q_values, dim=1).item())
            return best_action

    def update(self, batch_size: int = 32) -> Optional[float]:
        """
        Double DQN Bellman update step.
        """
        if len(self.replay_buffer) < batch_size:
            return None

        batch = self.replay_buffer.sample(batch_size)

        s = torch.tensor(batch.state, dtype=torch.float32, device=self.device)
        a = torch.tensor(batch.action, dtype=torch.int64, device=self.device).unsqueeze(1)
        r = torch.tensor(batch.reward, dtype=torch.float32, device=self.device).unsqueeze(1)
        s_next = torch.tensor(batch.next_state, dtype=torch.float32, device=self.device)
        done = torch.tensor(batch.done, dtype=torch.float32, device=self.device).unsqueeze(1)
        mask_next = torch.tensor(batch.next_mask, dtype=torch.bool, device=self.device)

        # Current Q-values: Q_online(s, a)
        curr_q = self.q_online(s).gather(1, a)

        with torch.no_grad():
            # Double DQN: action selected by online net with mask_next
            next_q_online = self.q_online(s_next, mask_next)
            best_next_actions = torch.argmax(next_q_online, dim=1, keepdim=True)

            # Target evaluated by target net
            next_q_target = self.q_target(s_next).gather(1, best_next_actions)
            target_q = r + (1.0 - done) * self.gamma * next_q_target

        loss = self.loss_fn(curr_q, target_q)

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.q_online.parameters(), max_norm=1.0)
        self.optimizer.step()

        self.train_steps += 1
        if self.train_steps % self.target_update_freq == 0:
            self.q_target.load_state_dict(self.q_online.state_dict())

        return float(loss.item())

    def save(self, path: str) -> None:
        torch.save(
            {
                "q_online": self.q_online.state_dict(),
                "q_target": self.q_target.state_dict(),
                "train_steps": self.train_steps,
            },
            path,
        )

    def load(self, path: str) -> None:
        ckpt = torch.load(path, map_location=self.device)
        self.q_online.load_state_dict(ckpt["q_online"])
        self.q_target.load_state_dict(ckpt["q_target"])
        self.train_steps = ckpt.get("train_steps", 0)


def train_agent(
    env: Any,
    agent: MaskedDoubleDQNAgent,
    n_episodes: int = 500,
    batch_size: int = 32,
    eps_start: float = 1.0,
    eps_end: float = 0.05,
    eps_decay: float = 0.995,
) -> Dict[str, List[float]]:
    """
    Train MaskedDoubleDQNAgent on Gymnasium-compliant ReasoningEnv.
    Returns training trajectory metrics (rewards, accuracy, costs, losses).
    """
    epsilon = eps_start
    history = {
        "episode_rewards": [],
        "accuracies": [],
        "token_costs": [],
        "losses": [],
    }

    for ep in range(n_episodes):
        obs, info = env.reset()
        mask = info.get("action_mask", np.ones(agent.action_dim, dtype=bool))
        ep_reward = 0.0
        ep_losses = []

        while True:
            action = agent.select_action(obs, mask, epsilon=epsilon)
            next_obs, reward, terminated, truncated, next_info = env.step(action)
            done = terminated or truncated
            next_mask = next_info.get("action_mask", np.ones(agent.action_dim, dtype=bool))

            agent.replay_buffer.push(obs, action, reward, next_obs, done, next_mask)
            ep_reward += reward

            loss = agent.update(batch_size=batch_size)
            if loss is not None:
                ep_losses.append(loss)

            obs = next_obs
            mask = next_mask

            if done:
                is_correct = float(next_info.get("is_correct", False))
                cost = float(next_info.get("total_cost", 0.0))
                history["accuracies"].append(is_correct)
                history["token_costs"].append(cost)
                break

        epsilon = max(eps_end, epsilon * eps_decay)
        history["episode_rewards"].append(ep_reward)
        if ep_losses:
            history["losses"].append(float(np.mean(ep_losses)))

    return history
