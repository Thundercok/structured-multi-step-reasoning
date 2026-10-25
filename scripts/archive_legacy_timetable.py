import hashlib
import shutil
from pathlib import Path

src = Path('rat/timetable')
dst = Path('audit/timetable_retirement_20261025/legacy_timetable')
dst.mkdir(parents=True, exist_ok=True)

manifest = []
for p in sorted(src.glob('*.py')):
    target = dst / p.name
    shutil.copy2(p, target)
    content = p.read_text(encoding='utf-8')
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest.append((p.name, len(content.splitlines()), h))

readme = Path('audit/timetable_retirement_20261025/README.md')
with open(readme, 'w', encoding='utf-8') as f:
    f.write('# Timetable Legacy Module Retirement & Spider Separation\n\n')
    f.write('**Date:** 2026-10-25\n\n')
    f.write('**Reason:** The canned Ton Duc Thang University (TDTU) specific crawler/fixtures were hardcoded to Ca 1-5 and fixed dates (September 2026). Scraping logic belongs strictly to `Thundercok/tdtu-timetable-compiler`. RAT requires a universal multi-mode schedule engine supporting both US/International clock-based systems (credit hours, start-end clock times, timezone) and period-based systems.\n\n')
    f.write('## SHA-256 Manifest\n\n')
    f.write('| File | Lines | SHA-256 |\n| :--- | :--- | :--- |\n')
    for name, lines, h in manifest:
        f.write(f'| `{name}` | {lines} | `{h}` |\n')

print(f'Successfully archived {len(manifest)} files to {dst}')
