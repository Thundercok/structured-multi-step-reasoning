import os
import tempfile
import numpy as np
import torch

from meta_controller.agent import MaskedDoubleDQNAgent, MaskedQNetwork, train_agent
from reasoning_env import A, ReasoningEnv
from test_reasoning_env import DATA, GOLD, MockLLM


def test_masked_q_network_outputs_neg_inf():
    net = MaskedQNetwork(state_dim=10, action_dim=7, hidden_dim=32)
    s = torch.randn(2, 10)
    mask = torch.tensor([[True, False, True, False, False, False, True],
                         [False, True, False, True, False, False, False]])
    q = net(s, mask)
    assert q.shape == (2, 7)
    # Check that masked actions have values <= -1e8
    assert q[0, 1].item() <= -1e8
    assert q[0, 3].item() <= -1e8
    assert q[0, 0].item() > -1e7
    assert q[1, 0].item() <= -1e8
    assert q[1, 1].item() > -1e7


def test_agent_never_selects_masked_action():
    agent = MaskedDoubleDQNAgent(state_dim=10, action_dim=7, hidden_dim=32, device="cpu")
    s = np.random.randn(10).astype(np.float32)
    # Only action 4 (PAL) and 6 (STOP) are allowed
    mask = np.array([False, False, False, False, True, False, True], dtype=bool)

    # Test both greedy (epsilon=0) and random exploratory (epsilon=1.0)
    for eps in [0.0, 0.5, 1.0]:
        for _ in range(50):
            action = agent.select_action(s, mask, epsilon=eps)
            assert action in (A.PAL, A.STOP), f"Selected forbidden action {action} with eps={eps}"


def test_agent_training_loop():
    llm = MockLLM(GOLD, deterministic=False, seed=42)
    env = ReasoningEnv(llm, DATA, lambda pred, gold: pred == gold, max_steps=3)
    agent = MaskedDoubleDQNAgent(state_dim=env.state_dim, action_dim=len(A), hidden_dim=64, lr=1e-3, device="cpu")

    # Run 60 training episodes
    history = train_agent(env, agent, n_episodes=60, batch_size=16)

    assert len(history["episode_rewards"]) == 60
    assert len(history["accuracies"]) == 60
    assert len(history["token_costs"]) == 60
    # Make sure at least some updates occurred and loss is recorded
    assert len(history["losses"]) > 0


def test_agent_save_and_load():
    agent1 = MaskedDoubleDQNAgent(state_dim=12, action_dim=7, hidden_dim=32, device="cpu")
    s = np.random.randn(12).astype(np.float32)
    mask = np.ones(7, dtype=bool)
    act1 = agent1.select_action(s, mask, epsilon=0.0)

    with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
        tmp_path = f.name

    try:
        agent1.save(tmp_path)
        agent2 = MaskedDoubleDQNAgent(state_dim=12, action_dim=7, hidden_dim=32, device="cpu")
        agent2.load(tmp_path)
        act2 = agent2.select_action(s, mask, epsilon=0.0)
        assert act1 == act2, "Loaded agent does not reproduce action of original agent"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
