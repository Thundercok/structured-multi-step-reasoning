"""Auxiliary CPU software check, not a real research collection entry point."""

import argparse
import json
from pathlib import Path

from experiments.cot_restart_fresh import MockSettings, run_mock, synthetic_dataset


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = run_mock(synthetic_dataset(), args.output,
                        MockSettings(base_cap=64, completion_cap=64, include_a=True))
    print(json.dumps({key: manifest[key] for key in (
        "status", "evidence", "original_groups", "completed_mock_calls", "real_model_calls",
        "total_synthetic_collection_tokens", "confirmatory", "stage_0_changed",
    )}))


if __name__ == "__main__":
    main()
