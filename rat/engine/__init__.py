"""
rat.engine — Context engineering, natural language parsing, and search engine.
"""

from importlib import import_module

_EXPORTS = {
    "ContextParser": "context_parser", "ParsedContext": "context_parser",
    "SearchEngine": "hybrid_search", "LLMClient": "llm_client",
    "Reranker": "reranker", "SearchResultItem": "reranker",
}


def __getattr__(name):
    """Keep the public exports without loading the full search/model stack."""
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value

__all__ = [
    "ContextParser",
    "ParsedContext",
    "SearchEngine",
    "LLMClient",
    "Reranker",
    "SearchResultItem",
]
