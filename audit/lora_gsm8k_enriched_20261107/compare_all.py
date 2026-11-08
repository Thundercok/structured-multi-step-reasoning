"""Run all comparison and report generation scripts for enriched GSM8K LoRA sweep.

Run from repo root:
    PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_enriched_20261107/compare_all.py
"""

import sys
from pathlib import Path

DIR = Path(__file__).parent


def main():
    print("=== [1/3] Running compare.py ===")
    from audit.lora_gsm8k_enriched_20261107 import compare
    compare.main()

    print("\n=== [2/3] Running compare_19_failing.py ===")
    from audit.lora_gsm8k_enriched_20261107 import compare_19_failing
    compare_19_failing.main()

    print("\n=== [3/3] Running report_generator.py ===")
    from audit.lora_gsm8k_enriched_20261107 import report_generator
    report_generator.main()

    print("\n=== All Enriched GSM8K Comparisons & Reports Completed Successfully ===")


if __name__ == "__main__":
    main()
