"""Compatibility command forwarding to the supported research smoke mode."""

import sys

from experiments.research_study import main as research_main


def main(argv=None):
    return research_main(["--cot-restart-fresh-smoke", *(sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    main()
