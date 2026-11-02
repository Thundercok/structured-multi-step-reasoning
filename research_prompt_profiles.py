"""Prompt text shared by research collection and artifact validation."""

ALIGNED_DIRECT_COT_SUFFIX_TEXT = {
    "DIRECT": (
        "\nAnswer directly without showing reasoning or intermediate steps. "
        "End with exactly one line 'Answer: ' followed only by the final answer "
        "(a number without units, one word/name, or an arithmetic expression)."
    ),
    "COT": (
        "\nWrite concise reasoning steps in plain English without markdown or LaTeX. "
        "End with exactly one line 'Answer: ' followed only by the final answer "
        "(a number without units, one word/name, or an arithmetic expression)."
    ),
}
