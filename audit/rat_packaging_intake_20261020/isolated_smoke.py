"""Run with the isolated interpreter's -I flag; no source checkout imports."""
import json
from pathlib import Path
import sys

import document_intake
from document_intake.pdf import PDFReadError, read_pdf
from document_intake.tesseract import TesseractOCREngine
from document_intake.vision import recognize_tokens

location = Path(document_intake.__file__).resolve()
assert 'isolated-venv' in str(location), location
assert not any(name in sys.modules for name in ('rat', 'PyQt6', 'objc', 'pypdf', 'PIL', 'mlx', 'mlx_lm'))
try:
    read_pdf('/not-an-input.pdf')
except PDFReadError as exc:
    assert exc.code == 'pdf_engine_unavailable', exc.code
else:
    raise AssertionError('Optional PDF engine unexpectedly installed')
assert TesseractOCREngine().run_ocr('/not-an-input.png') == {'full_text': '', 'lines': [], 'tokens': []}
print(json.dumps({'status': 'passed', 'package_location': str(location),
                  'optional_engines': 'not installed', 'model_calls': 0}))
