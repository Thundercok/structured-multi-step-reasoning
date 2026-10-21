"""Real PDFKit on authored digital/error fixtures, with all OCR blocked."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from document_intake import pdf, vision

ocr_attempts = []
def blocked_ocr(*args, **kwargs):
    ocr_attempts.append(True)
    raise AssertionError('OCR is not authorized in this native digital-reader smoke')
vision.recognize_tokens = blocked_ocr

text = pdf.read_pdf_native(str(HERE / 'fixtures/digital.pdf'))
assert text and '--- Page 1 ---\nShort' in text and '--- Page 2 ---\nSecond page' in text, text
assert len(pdf.read_pdf_native(str(HERE / 'fixtures/digital.pdf'), max_chars=10)) <= 10
outcomes = {}
for name in ('encrypted.pdf', 'malformed.pdf', 'zero-pages.pdf'):
    value = pdf.read_pdf_native(str(HERE / 'fixtures' / name))
    assert value in (None, ''), (name, value)
    outcomes[name] = value
assert not ocr_attempts, ocr_attempts
result = {'status': 'passed', 'native_engine': 'macOS PDFKit',
          'digital_pages': 2, 'error_or_empty_outputs': outcomes,
          'ocr_attempts': len(ocr_attempts), 'model_calls': 0,
          'scope': 'authored digital/error fixtures; no OCR quality or GUI acceptance'}
(HERE / 'native_pdf_validation.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
