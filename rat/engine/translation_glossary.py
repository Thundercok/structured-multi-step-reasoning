"""Academic term protection for on-device English → Vietnamese translation.

The bundled MT model mistranslates research vocabulary ("Transformer" becomes
"người biến hình"). Known terms are swapped for short placeholders the model
copies through unchanged, then rendered the way Vietnamese students read them:
an established Vietnamese term with the English in parentheses, or the English
term alone when that is what people actually say.
"""
from __future__ import annotations

import re

# English term -> rendering. Longest terms are matched first.
GLOSSARY = {
    'multi-head self-attention': 'tự chú ý đa đầu (multi-head self-attention)',
    'self-attention': 'tự chú ý (self-attention)',
    'multi-head attention': 'chú ý đa đầu (multi-head attention)',
    'multi-head': 'đa đầu (multi-head)',
    'attention mechanism': 'cơ chế chú ý (attention)',
    'attention': 'cơ chế chú ý (attention)',
    'transformer': 'Transformer',
    'large language model': 'mô hình ngôn ngữ lớn (LLM)',
    'language model': 'mô hình ngôn ngữ',
    'neural network': 'mạng nơ-ron',
    'convolutional neural network': 'mạng nơ-ron tích chập (CNN)',
    'recurrent neural network': 'mạng nơ-ron hồi quy (RNN)',
    'graph neural network': 'mạng nơ-ron đồ thị (GNN)',
    'recurrence': 'cơ chế hồi quy (recurrence)',
    'recurrent': 'hồi quy (recurrent)',
    'convolutional': 'tích chập (convolutional)',
    'convolution': 'phép tích chập (convolution)',
    'encoder-decoder': 'encoder-decoder',
    'encoder': 'bộ mã hóa (encoder)',
    'decoder': 'bộ giải mã (decoder)',
    'embedding': 'embedding',
    'token': 'token',
    'tokenizer': 'tokenizer',
    'fine-tuning': 'tinh chỉnh (fine-tuning)',
    'fine-tune': 'tinh chỉnh (fine-tune)',
    'training': 'huấn luyện',
    'train': 'huấn luyện',
    'controller': 'bộ điều khiển (controller)',
    'checker': 'bộ kiểm tra (checker)',
    'pre-training': 'tiền huấn luyện (pre-training)',
    'pretraining': 'tiền huấn luyện (pre-training)',
    'baseline': 'mô hình cơ sở (baseline)',
    'benchmark': 'benchmark',
    'dataset': 'tập dữ liệu',
    'perplexity': 'perplexity',
    'gradient descent': 'hạ gradient (gradient descent)',
    'backpropagation': 'lan truyền ngược (backpropagation)',
    'loss function': 'hàm mất mát (loss function)',
    'overfitting': 'quá khớp (overfitting)',
    'regularization': 'chính quy hóa (regularization)',
    'dropout': 'dropout',
    'hyperparameter': 'siêu tham số (hyperparameter)',
    'reinforcement learning': 'học tăng cường (reinforcement learning)',
    'supervised learning': 'học có giám sát',
    'unsupervised learning': 'học không giám sát',
    'machine learning': 'học máy',
    'deep learning': 'học sâu',
    'chain-of-thought': 'chuỗi suy luận (chain-of-thought)',
    'inference': 'suy luận (inference)',
    'latency': 'độ trễ (latency)',
    'throughput': 'thông lượng (throughput)',
    'state-of-the-art': 'hiện đại nhất (state-of-the-art)',
    'ablation study': 'thí nghiệm loại bỏ (ablation)',
    'ablation': 'thí nghiệm loại bỏ (ablation)',
    'sequence transduction': 'chuyển đổi chuỗi (sequence transduction)',
    'machine translation': 'dịch máy',
    'precision': 'precision',
    'recall': 'recall',
    'f1 score': 'F1',
    'accuracy': 'độ chính xác (accuracy)',
    'classifier': 'bộ phân loại (classifier)',
    'regression': 'hồi quy (regression)',
    'spatio-temporal': 'không gian - thời gian (spatio-temporal)',
    'optimal stopping': 'dừng tối ưu (optimal stopping)',
    'heuristic': 'heuristic',
    'random seed': 'seed',
    'seed': 'seed',
}

_PATTERN = re.compile(
    r'(?<![\w-])(' + '|'.join(re.escape(t) for t in sorted(GLOSSARY, key=len, reverse=True)) + r')(?:s|es)?(?![\w-])',
    re.IGNORECASE)


def protect(text):
    """Replace known terms with placeholders; returns (text, placeholder -> rendering)."""
    # Pick a placeholder letter the source does not already use as "<letter><digits>".
    letter = next(c for c in 'TKQZ' if not re.search(rf'\b{c}\d+\b', text))
    mapping, renderings = {}, {}

    def swap(match):
        rendering = GLOSSARY[match.group(1).lower()]
        key = renderings.get(rendering)
        if key is None:
            key = f'{letter}{len(renderings) + 1}'
            renderings[rendering] = key
            mapping[key] = rendering
        return key

    return _PATTERN.sub(swap, text), mapping


def restore(text, mapping):
    if not mapping:
        return text
    letter = next(iter(mapping))[0]
    text = re.sub(rf'\b{letter}\d+\b', lambda m: mapping.get(m.group(0), m.group(0)), text)
    # A rendering that opens a sentence must start with a capital letter.
    return re.sub(r'(^|[.!?]\s+)([a-zà-ỹđ])', lambda m: m.group(1) + m.group(2).upper(), text)
