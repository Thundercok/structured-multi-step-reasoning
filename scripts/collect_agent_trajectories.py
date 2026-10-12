"""Collect raw RAT development traces; human review supplies quality labels.

This entry point intentionally does not turn tool presence into PRODUCTIVE,
WASTEFUL or PREMATURE training labels. See docs/rat_assistant_development.md.
"""
from scripts.eval_assistant_agent import main


if __name__ == '__main__':
    main()
