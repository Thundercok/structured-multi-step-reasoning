"""MLX Generator Backend for MSRA Streaming Runtime.

Connects MSRAStepDriver directly to Apple Silicon MLX language models
and fine-tuned LoRA adapters with incremental token streaming and early stop detection.
"""

from typing import Any, Callable, Dict, List, Optional


class MLXGeneratorBackend:
    """Generator backend powered by MLX Language Models (mlx_lm).

    Streams tokens until one of the specified stop_sequences is encountered,
    allowing interactive tool routing at intermediate decision boundaries.
    """

    def __init__(
        self,
        model: Any = None,
        tokenizer: Any = None,
        model_path: Optional[str] = None,
        adapter_path: Optional[str] = None,
        temperature: float = 0.0,
        sampler: Optional[Callable] = None,
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.model_path = model_path
        self.adapter_path = adapter_path
        self.temperature = temperature
        self.sampler = sampler

    def _ensure_loaded(self):
        """Lazy load model and tokenizer if not provided at initialization."""
        if self.model is None or self.tokenizer is None:
            if not self.model_path:
                raise ValueError("Neither model/tokenizer nor model_path was provided.")
            from mlx_lm import load
            from structured_llm.evaluate import MODEL_ID, model_path
            resolved_path = model_path() if self.model_path == MODEL_ID else self.model_path
            self.model, self.tokenizer = load(
                resolved_path,
                adapter_path=self.adapter_path,
            )

    def generate_until(
        self,
        prompt: str,
        stop_sequences: List[str],
        max_new_tokens: int = 512,
    ) -> str:
        """Stream tokens from MLX model until any stop sequence in stop_sequences is matched."""
        self._ensure_loaded()
        from mlx_lm import stream_generate

        accumulated = ""
        for response in stream_generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=max_new_tokens,
            sampler=self.sampler,
            verbose=False,
        ):
            accumulated += response.text

            # Check if any stop sequence has appeared
            earliest_idx = -1
            matched_stop = None
            for stop in stop_sequences:
                if stop in accumulated:
                    idx = accumulated.index(stop) + len(stop)
                    if earliest_idx == -1 or idx < earliest_idx:
                        earliest_idx = idx
                        matched_stop = stop

            if earliest_idx != -1:
                return accumulated[:earliest_idx]

        return accumulated
