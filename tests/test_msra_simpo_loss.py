"""Unit tests for SimPO loss implementation."""

import math
import numpy as np
import pytest
from structured_llm.msra.simpo_loss import (
    compute_token_logps_numpy,
    simpo_loss_scalar,
)


def test_simpo_loss_scalar_preferred_chosen():
    # Chosen has -10 logp over 10 tokens (avg -1.0)
    # Rejected has -30 logp over 10 tokens (avg -3.0)
    res = simpo_loss_scalar(
        chosen_logp=-10.0,
        rejected_logp=-30.0,
        chosen_len=10,
        rejected_len=10,
        beta=2.0,
        gamma=0.5,
    )
    # r_w = 2.0 * (-1.0) = -2.0
    # r_l = 2.0 * (-3.0) = -6.0
    # margin = -2.0 - (-6.0) = 4.0
    # effective_margin = 4.0 - 0.5 = 3.5
    # loss = log(1 + exp(-3.5)) ~ 0.0298
    assert res.accuracy == 1.0
    assert abs(res.chosen_reward - (-2.0)) < 1e-6
    assert abs(res.rejected_reward - (-6.0)) < 1e-6
    assert abs(res.reward_margin - 4.0) < 1e-6
    expected_loss = math.log1p(math.exp(-3.5))
    assert abs(res.loss - expected_loss) < 1e-6
    assert res.loss < 0.05


def test_simpo_loss_scalar_dispreferred_chosen():
    # Chosen has lower avg logp than rejected
    res = simpo_loss_scalar(
        chosen_logp=-40.0,
        rejected_logp=-10.0,
        chosen_len=10,
        rejected_len=10,
        beta=2.0,
        gamma=0.5,
    )
    # r_w = -8.0, r_l = -2.0 -> margin = -6.0
    # effective_margin = -6.5
    assert res.accuracy == 0.0
    assert res.reward_margin < 0
    # loss should be large (-effective_margin + log1p(exp(effective_margin))) ~ 6.5
    assert res.loss > 6.0


def test_simpo_length_normalization():
    # Test that a shorter response with same average logp has same reward
    # Response A: len 5, logp -5.0 (avg -1.0)
    # Response B: len 20, logp -20.0 (avg -1.0)
    res = simpo_loss_scalar(
        chosen_logp=-5.0,
        rejected_logp=-20.0,
        chosen_len=5,
        rejected_len=20,
        beta=2.0,
        gamma=0.5,
    )
    # r_w == r_l == -2.0 -> margin == 0.0
    assert abs(res.reward_margin) < 1e-6
    # effective_margin = -0.5 -> loss = log(1 + exp(0.5)) ~ 0.974
    expected_loss = math.log1p(math.exp(0.5))
    assert abs(res.loss - expected_loss) < 1e-6


def test_compute_token_logps_numpy():
    # 2 tokens, vocab size 3
    logits = np.array([
        [10.0, 0.0, 0.0],  # strongly predicts token 0
        [0.0, 10.0, 0.0],  # strongly predicts token 1
    ])
    labels = np.array([0, 1])
    total_logp, count = compute_token_logps_numpy(logits, labels)
    assert count == 2
    # log prob for token 0 and token 1 should be very close to 0 (since exp(10) dominates)
    assert total_logp > -0.01

    # With mask ignoring token 0
    mask = np.array([0.0, 1.0])
    masked_logp, masked_count = compute_token_logps_numpy(logits, labels, mask=mask)
    assert masked_count == 1
    assert masked_logp > -0.01
