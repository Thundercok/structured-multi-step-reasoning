# Timetable Legacy Module Retirement & Spider Separation

**Date:** 2026-10-25

**Reason:** The canned Ton Duc Thang University (TDTU) specific crawler/fixtures were hardcoded to Ca 1-5 and fixed dates (September 2026). Scraping logic belongs strictly to `Thundercok/tdtu-timetable-compiler`. RAT requires a universal multi-mode schedule engine supporting both US/International clock-based systems (credit hours, start-end clock times, timezone) and period-based systems.

## SHA-256 Manifest

| File | Lines | SHA-256 |
| :--- | :--- | :--- |
| `__init__.py` | 31 | `4522e4a497453ad482b991fcb8eb020b299398fa57a5cbe5a37da0b49d309ba1` |
| `compositor.py` | 798 | `63f8d8022b3cee0469ab1a27d6c53937c48c2a95492594fff083c4c5f5f08493` |
| `data.py` | 239 | `c630a387a8f14b957ad62988dcee01582b77bb7ddbfe96d8283a034c8d576417` |
| `model.py` | 247 | `20ab7b61066405d893ecb3682a634bf810d14443321e1f61bffc3942a632abd7` |
