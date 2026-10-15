"""Synthetic on-device smoke; no personal files or model requests."""
from pathlib import Path
import json
import logging
logging.basicConfig(level=logging.WARNING)
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PIL import Image, ImageDraw, ImageFont
from document_intake.vision import recognize_tokens
from document_intake.tesseract import TesseractOCREngine
from document_intake.pdf import read_pdf_native, read_pdf
out = Path(__file__).resolve().parent
image = Image.new('RGB', (1600, 650), 'white')
draw = ImageDraw.Draw(image)
font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 64)
for i, line in enumerate(['Subtotal: 100000', 'Tax: 10000', 'Total: 110000']):
    draw.text((80, 70 + 150*i), line, font=font, fill='black')
path = out / 'synthetic_invoice.png'
image.save(path)
scan = out / 'synthetic_scan.pdf'
image.save(scan, 'PDF')
vision = recognize_tokens(path)
vision_bytes = recognize_tokens(path.read_bytes())
tess = TesseractOCREngine().run_ocr(str(path))
native = read_pdf_native(str(scan))
digital = read_pdf(scan)
result = {'fixture': 'synthetic smoke, not corpus accuracy evidence', 'vision_tokens': vision,
          'vision_bytes_tokens': vision_bytes, 'tesseract': tess, 'pdf_native': native, 'pdf_digital': digital}
(out / 'live_smoke.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
assert len(vision) and len(vision_bytes) and len(tess['tokens'])
assert native and '110000' in native
assert digital['full_text'] == ''
print(json.dumps({'vision_tokens': len(vision), 'vision_bytes_tokens': len(vision_bytes),
                  'tesseract_tokens': len(tess['tokens']), 'scanned_pdf_ocr': True}))
