"""SimPO (Simple Preference Optimization) Objective and Loss Functions.

Implements reference-free preference optimization (Meng et al., NeurIPS 2024):
    L_SimPO(theta) = -E_{(x, y_w, y_l)} [ log sigma( (beta/|y_w|) log pi_theta(y_w|x)
                                                  - (beta/|y_l|) log pi_theta(y_l|x)
                                                  - gamma ) ]

Key advantage for 16 GB Apple Silicon:
- SimPO eliminates the reference model pi_ref, reducing memory footprint by ~50%
  compared to standard DPO while achieving higher alignment accuracy and avoiding
  length-bias degeneration via explicit average token log-likelihood normalization.
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class SimPOResult:
    """Detailed outputs from a SimPO loss step."""
    loss: float
    chosen_reward: float
    rejected_reward: float
    reward_margin: float
    accuracy: float  # 1.0 if chosen_reward > rejected_reward else 0.0


def simpo_loss_scalar(
    chosen_logp: float,
    rejected_logp: float,
    chosen_len: int,
    rejected_len: int,
    beta: float = 2.0,
    gamma: float = 0.5,
) -> SimPOResult:
    """Compute SimPO loss and reward metrics for a single (chosen, rejected) pair.

    Args:
        chosen_logp: Sum of log probabilities of chosen tokens log pi(y_w | x).
        rejected_logp: Sum of log probabilities of rejected tokens log pi(y_l | x).
        chosen_len: Number of tokens in chosen response |y_w|.
        rejected_len: Number of tokens in rejected response |y_l|.
        beta: Reward scaling temperature parameter (default: 2.0).
        gamma: Target reward margin offset parameter (default: 0.5).

    Returns:
        SimPOResult with scalar loss, rewards, margin, and accuracy.
    """
    len_w = max(1, chosen_len)
    len_l = max(1, rejected_len)

    # Length-normalized average log-likelihoods
    r_w = beta * (chosen_logp / len_w)
    r_l = beta * (rejected_logp / len_l)

    # Margin with gamma penalty
    margin = r_w - r_l
    effective_margin = margin - gamma

    # Numerically stable -log(sigmoid(effective_margin))
    # -log(1 / (1 + e^-z)) = log(1 + e^-z) = softplus(-z)
    if effective_margin >= 0:
        loss = math.log1p(math.exp(-effective_margin))
    else:
        loss = -effective_margin + math.log1p(math.exp(effective_margin))

    acc = 1.0 if r_w > r_l else 0.0

    return SimPOResult(
        loss=loss,
        chosen_reward=r_w,
        rejected_reward=r_l,
        reward_margin=margin,
        accuracy=acc,
    )


def compute_token_logps_numpy(logits: Any, labels: Any, mask: Optional[Any] = None) -> Tuple[float, int]:
    """Compute sum of log probabilities and token count using NumPy.

    Args:
        logits: Shape (seq_len, vocab_size).
        labels: Shape (seq_len,) target token indices.
        mask: Optional binary mask (seq_len,) where 1 indicates response tokens.
    """
    import numpy as np

    # Log-softmax along vocab axis
    max_l = np.max(logits, axis=-1, keepdims=True)
    exp_l = np.exp(logits - max_l)
    log_probs = (logits - max_l) - np.log(np.sum(exp_l, axis=-1, keepdims=True))

    # Gather log prob of target labels
    token_logps = np.take_along_axis(log_probs, labels[:, None], axis=-1).squeeze(-1)

    if mask is not None:
        token_logps = token_logps * mask
        num_tokens = int(np.sum(mask))
    else:
        num_tokens = len(labels)

    total_logp = float(np.sum(token_logps))
    return total_logp, num_tokens


def simpo_loss_mlx(
    chosen_logps: Any,
    rejected_logps: Any,
    chosen_lens: Any,
    rejected_lens: Any,
    beta: float = 2.0,
    gamma: float = 0.5,
) -> Tuple[Any, Dict[str, Any]]:
    """Compute batched SimPO loss using Apple MLX.

    Args:
        chosen_logps: Array of shape (batch_size,) containing sum of log probs.
        rejected_logps: Array of shape (batch_size,) containing sum of log probs.
        chosen_lens: Array of shape (batch_size,) containing token lengths.
        rejected_lens: Array of shape (batch_size,) containing token lengths.
        beta: SimPO temperature.
        gamma: SimPO margin.

    Returns:
        (loss, metrics_dict) where loss is an MLX scalar.
    """
    import mlx.core as mx

    # Avoid division by zero
    chosen_lens = mx.maximum(chosen_lens, 1)
    rejected_lens = mx.maximum(rejected_lens, 1)

    # Average log probabilities (length-normalized rewards)
    r_w = beta * (chosen_logps / chosen_lens)
    r_l = beta * (rejected_logps / rejected_lens)

    margin = r_w - r_l
    logits = margin - gamma

    # -log(sigmoid(logits)) = log(1 + exp(-logits)) = nn.softplus(-logits)
    loss = mx.mean(mx.logaddexp(mx.zeros_like(logits), -logits))

    # Metrics
    acc = mx.mean((r_w > r_l).astype(mx.float32))

    metrics = {
        "loss": float(loss.item()),
        "chosen_reward": float(mx.mean(r_w).item()),
        "rejected_reward": float(mx.mean(r_l).item()),
        "reward_margin": float(mx.mean(margin).item()),
        "accuracy": float(acc.item()),
    }
    return loss, metrics


def compute_log_probs(
    logits: Any,
    targets: Any,
    mask: Any,
) -> Tuple[Any, Any]:
    """Compute per-sequence total log-probabilities and sequence lengths for response tokens in MLX."""
    import mlx.core as mx
    import mlx.nn as nn

    ce = nn.losses.cross_entropy(logits, targets)
    token_log_probs = -ce * mask
    total_log_probs = mx.sum(token_log_probs, axis=-1)
    seq_lens = mx.sum(mask, axis=-1)
    seq_lens = mx.maximum(seq_lens, 1.0)
    return total_log_probs, seq_lens


def compute_simpo_loss(
    logits_chosen: Any,
    targets_chosen: Any,
    mask_chosen: Any,
    logits_rejected: Any,
    targets_rejected: Any,
    mask_rejected: Any,
    beta: float = 2.0,
    gamma: float = 0.5,
) -> Tuple[Any, Dict[str, float]]:
    """Compute end-to-end SimPO loss directly from model logits and target tokens."""
    log_p_w, len_w = compute_log_probs(logits_chosen, targets_chosen, mask_chosen)
    log_p_l, len_l = compute_log_probs(logits_rejected, targets_rejected, mask_rejected)
    return simpo_loss_mlx(log_p_w, log_p_l, len_w, len_l, beta=beta, gamma=gamma)
