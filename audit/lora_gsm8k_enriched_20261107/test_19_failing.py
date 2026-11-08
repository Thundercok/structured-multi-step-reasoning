"""Inspect the 19 failing questions identified in error_reading.md on the new enriched models.

Wrapper for compare_19_failing.py.
"""

from audit.lora_gsm8k_enriched_20261107.compare_19_failing import main

if __name__ == "__main__":
    main()
