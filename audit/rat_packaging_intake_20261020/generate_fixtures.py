"""Persist six authored input PDFs and one raster source; no real documents."""
import importlib.util
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('intake_fixture_tests', ROOT / 'tests/test_document_intake_robustness.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
fixtures = HERE / 'fixtures'
fixtures.mkdir(exist_ok=False)
helpers.text_pdf(fixtures / 'digital.pdf')
helpers.text_pdf(fixtures / 'encrypted.pdf', password='fixture-password')
helpers.text_pdf(fixtures / 'zero-pages.pdf', texts=())
writer = helpers.PdfWriter()
writer.add_blank_page(100, 100)
writer.write(fixtures / 'blank-page.pdf')
(fixtures / 'malformed.pdf').write_bytes(b'%PDF-1.7\ntruncated authored fixture')
image = Image.new('RGB', (600, 200), 'white')
ImageDraw.Draw(image).text((30, 70), 'Authored scan fixture 123', fill='black', font_size=28)
image.save(fixtures / 'scan-source.png')
image.save(fixtures / 'scanned.pdf', 'PDF')
results = {}
for path in sorted(fixtures.glob('*.pdf')):
    try:
        value = helpers.read_pdf(path)
        results[path.name] = {key: value[key] for key in ('total_pages', 'full_text', 'status', 'extraction_truncated')}
    except helpers.PDFReadError as exc:
        results[path.name] = {'error_code': exc.code}
(HERE / 'fixture_results.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
