"""Academic term protection for on-device translation (English ↔ Vietnamese).

The bundled MT model mistranslates research vocabulary ("Transformer" becomes
"người biến hình", "mạng nơ-ron tích chập" becomes "short-lived neurons network").
Known terms are swapped for short placeholders the model copies through unchanged,
then rendered the way researchers and students read them: established academic terms
with English abbreviations in parentheses, or the recognized term alone.
"""
from __future__ import annotations

import re

# English term -> Vietnamese rendering. Longest terms are matched first.
GLOSSARY = {
    'multi-head self-attention': 'tự chú ý đa đầu (multi-head self-attention)',
    'self-attention': 'tự chú ý (self-attention)',
    'multi-head attention': 'chú ý đa đầu (multi-head attention)',
    'multi-head': 'đa đầu (multi-head)',
    'scaled dot-product attention': 'chú ý tích vô hướng theo tỉ lệ (scaled dot-product attention)',
    'cross-attention': 'chú ý chéo (cross-attention)',
    'cross attention': 'chú ý chéo (cross-attention)',
    'attention mechanism': 'cơ chế chú ý (attention)',
    'attention': 'cơ chế chú ý (attention)',
    'transformer': 'Transformer',
    'large language model': 'mô hình ngôn ngữ lớn (LLM)',
    'language model': 'mô hình ngôn ngữ',
    'neural network': 'mạng nơ-ron',
    'convolutional neural network': 'mạng nơ-ron tích chập (CNN)',
    'recurrent neural network': 'mạng nơ-ron hồi quy (RNN)',
    'graph neural network': 'mạng nơ-ron đồ thị (GNN)',
    'feed-forward network': 'mạng truyền thẳng (feed-forward network)',
    'feed forward network': 'mạng truyền thẳng (feed-forward network)',
    'feed-forward networks': 'mạng truyền thẳng (feed-forward networks)',
    'feed forward networks': 'mạng truyền thẳng (feed-forward networks)',
    'feed-forward': 'truyền thẳng (feed-forward)',
    'feed forward': 'truyền thẳng (feed-forward)',
    'residual connection': 'kết nối phần dư (residual connection)',
    'residual connections': 'kết nối phần dư (residual connections)',
    'layer normalization': 'chuẩn hóa từng tầng (layer normalization)',
    'layer norm': 'chuẩn hóa từng tầng (layer norm)',
    'positional encoding': 'mã hóa vị trí (positional encoding)',
    'positional embeddings': 'mã hóa vị trí (positional embeddings)',
    'positional embedding': 'mã hóa vị trí (positional embedding)',
    'context window': 'cửa sổ ngữ cảnh (context window)',
    'vector space': 'không gian vector (vector space)',
    'cosine similarity': 'độ tương đồng cosine (cosine similarity)',
    'nearest neighbor': 'láng giềng gần nhất (nearest neighbor)',
    'nearest neighbors': 'láng giềng gần nhất (nearest neighbors)',
    'learning rate': 'tốc độ học (learning rate)',
    'weight decay': 'suy giảm trọng số (weight decay)',
    'cross-entropy': 'hàm mất mát cross-entropy (cross-entropy)',
    'cross entropy': 'hàm mất mát cross-entropy (cross-entropy)',
    'ground truth': 'dữ liệu chuẩn thực tế (ground truth)',
    'data augmentation': 'tăng cường dữ liệu (data augmentation)',
    'greedy decoding': 'giải mã tham lam (greedy decoding)',
    'beam search': 'tìm kiếm chùm (beam search)',
    'prompt engineering': 'thiết kế câu lệnh gợi ý (prompt engineering)',
    'prompt': 'câu lệnh gợi ý (prompt)',
    'self-supervised learning': 'học tự giám sát (self-supervised learning)',
    'self-supervised': 'tự giám sát (self-supervised)',
    'autoencoder': 'bộ tự mã hóa (autoencoder)',
    'latent space': 'không gian ẩn (latent space)',
    'embedding space': 'không gian embedding (embedding space)',
    'loss landscape': 'bề mặt hàm mất mát (loss landscape)',
    'gradient clipping': 'cắt ngưỡng gradient (gradient clipping)',
    'activation function': 'hàm kích hoạt (activation function)',
    'pooling': 'phép gộp (pooling)',
    'mean pooling': 'phép gộp trung bình (mean pooling)',
    'max pooling': 'phép gộp cực đại (max pooling)',
    'quantization': 'lượng tử hóa (quantization)',
    'pruning': 'cắt tỉa mô hình (pruning)',
    'knowledge distillation': 'chưng cất tri thức (knowledge distillation)',
    'distillation': 'chưng cất tri thức (distillation)',
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

# Vietnamese term -> English rendering.
VI_EN_GLOSSARY = {
    'mạng nơ-ron tích chập': 'convolutional neural network (CNN)',
    'mạng nơ ron tích chập': 'convolutional neural network (CNN)',
    'mạng nơ-ron hồi quy': 'recurrent neural network (RNN)',
    'mạng nơ ron hồi quy': 'recurrent neural network (RNN)',
    'mạng nơ-ron đồ thị': 'graph neural network (GNN)',
    'mạng nơ ron đồ thị': 'graph neural network (GNN)',
    'mạng nơ-ron': 'neural network',
    'mạng nơ ron': 'neural network',
    'cơ chế tự chú ý đa đầu': 'multi-head self-attention mechanism',
    'tự chú ý đa đầu': 'multi-head self-attention',
    'chú ý đa đầu': 'multi-head attention',
    'cơ chế chú ý': 'attention mechanism',
    'tự chú ý': 'self-attention',
    'mô hình ngôn ngữ lớn': 'large language model (LLM)',
    'mô hình ngôn ngữ': 'language model',
    'chuỗi suy luận': 'chain-of-thought (CoT)',
    'lan truyền ngược': 'backpropagation',
    'hạ gradient': 'gradient descent',
    'hàm mất mát': 'loss function',
    'quá khớp': 'overfitting',
    'chính quy hóa': 'regularization',
    'dừng tối ưu': 'optimal stopping',
    'học tăng cường': 'reinforcement learning',
    'học có giám sát': 'supervised learning',
    'học không giám sát': 'unsupervised learning',
    'học tự giám sát': 'self-supervised learning',
    'học chuyển giao': 'transfer learning',
    'học đối chiếu': 'contrastive learning',
    'học sâu': 'deep learning',
    'học máy': 'machine learning',
    'tinh chỉnh': 'fine-tuning',
    'tiền huấn luyện': 'pre-training',
    'huấn luyện': 'training',
    'suy luận': 'inference',
    'độ trễ': 'latency',
    'thông lượng': 'throughput',
    'thí nghiệm loại bỏ': 'ablation study',
    'bộ mã hóa': 'encoder',
    'bộ giải mã': 'decoder',
    'mã hóa vị trí': 'positional encoding',
    'mạng truyền thẳng': 'feed-forward network',
    'kết nối phần dư': 'residual connection',
    'chuẩn hóa từng tầng': 'layer normalization',
    'chú ý chéo': 'cross-attention',
    'cửa sổ ngữ cảnh': 'context window',
    'không gian vector': 'vector space',
    'độ tương đồng cosine': 'cosine similarity',
    'tốc độ học': 'learning rate',
    'suy giảm trọng số': 'weight decay',
    'tăng cường dữ liệu': 'data augmentation',
    'giải mã tham lam': 'greedy decoding',
    'tìm kiếm chùm': 'beam search',
    'câu lệnh gợi ý': 'prompt',
    'hàm kích hoạt': 'activation function',
    'phép gộp': 'pooling',
    'lượng tử hóa': 'quantization',
    'cắt tỉa mô hình': 'pruning',
    'chưng cất tri thức': 'knowledge distillation',
    'tập dữ liệu': 'dataset',
    'độ chính xác': 'accuracy',
    'mô hình cơ sở': 'baseline',
}

_EN_VI_PATTERN = re.compile(
    r'(?<![\w-])(' + '|'.join(re.escape(t) for t in sorted(GLOSSARY, key=len, reverse=True)) + r')(?:s|es)?(?![\w-])',
    re.IGNORECASE)

_VI_EN_PATTERN = re.compile(
    r'(?<![0-9a-zA-Zà-ỹÀ-ỸđĐ_])(' + '|'.join(re.escape(t) for t in sorted(VI_EN_GLOSSARY, key=len, reverse=True)) + r')(?![0-9a-zA-Zà-ỹÀ-ỸđĐ_])',
    re.IGNORECASE)


# Everyday English words that are only terms in research text: "the train leaves",
# "pay attention", "recall your token" must reach the model untouched.
AMBIGUOUS_EN = {'train', 'training', 'attention', 'token', 'recall', 'precision', 'accuracy', 'seed', 'baseline',
                'inference', 'regression', 'controller', 'checker', 'encoder', 'decoder', 'convolution', 'recurrence'}
_RESEARCH_CONTEXT = re.compile(r'\b(?:models?|neural|networks?|algorithms?|experiments?|evaluat\w+|parameters?|'
                               r'optimi[sz]\w+|predict\w+|learning|paper)\b', re.IGNORECASE)
_ARTICLE_BEFORE = re.compile(r'\b(?:the|a|an|this|that|my|our|your)\s+$', re.IGNORECASE)


def protect(text: str, source: str = 'en', target: str = 'vi') -> tuple[str, dict[str, str]]:
    """Replace known terms with placeholders; returns (text, placeholder -> rendering)."""
    if source == 'en' and target == 'vi':
        pattern = _EN_VI_PATTERN
        lookup = GLOSSARY
    elif source == 'vi' and target == 'en':
        pattern = _VI_EN_PATTERN
        lookup = VI_EN_GLOSSARY
    else:
        return text, {}

    # Pick a placeholder letter the source does not already use as "<letter><digits>".
    letter = next(c for c in 'TKQZ' if not re.search(rf'\b{c}\d+\b', text))
    mapping, renderings = {}, {}
    research = source != 'en' or bool(_RESEARCH_CONTEXT.search(text)) or any(
        m.group(1).lower() not in AMBIGUOUS_EN for m in pattern.finditer(text))

    def swap(match):
        term = match.group(1).lower()
        rendering = lookup.get(term)
        if not rendering:
            return match.group(0)
        if source == 'en' and term in AMBIGUOUS_EN and not research:
            return match.group(0)
        # "the train" is a noun even in a paper; the verb is what means huấn luyện.
        if source == 'en' and term == 'train' and _ARTICLE_BEFORE.search(text[:match.start()]):
            return match.group(0)
        key = renderings.get(rendering)
        if key is None:
            key = f'{letter}{len(renderings) + 1}'
            renderings[rendering] = key
            mapping[key] = rendering
        return key

    return pattern.sub(swap, text), mapping


def restore(text: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return text
    letter = next(iter(mapping))[0]
    text = re.sub(rf'\b{letter}\d+\b', lambda m: mapping.get(m.group(0), m.group(0)), text)
    # A rendering that opens a sentence must start with a capital letter.
    return re.sub(r'(^|[.!?]\s+)([a-zà-ỹđ])', lambda m: m.group(1) + m.group(2).upper(), text)
