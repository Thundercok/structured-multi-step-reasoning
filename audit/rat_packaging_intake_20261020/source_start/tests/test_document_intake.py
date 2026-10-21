"""Shared intake contracts; generated fixtures are not OCR quality evidence."""
import subprocess
import sys
from types import SimpleNamespace as NS

import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from document_intake.pdf import read_pdf
from document_intake.tesseract import TesseractOCREngine


def make_pdf(path):
    writer = PdfWriter()
    for text in ('First page contents', 'Second page contents'):
        page = writer.add_blank_page(600, 800)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({
            NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f'BT /F1 12 Tf 30 750 Td ({text}) Tj ET'.encode())
        page[NameObject('/Contents')] = writer._add_object(stream)
    writer.add_metadata({'/Title': 'Synthetic document'})
    writer.write(path)


def test_digital_pdf_pages_metadata_and_limits(tmp_path):
    path = tmp_path / 'test.pdf'
    make_pdf(path)
    result = read_pdf(path, max_pages=1)
    assert result['total_pages'] == 2 and result['extraction_truncated']
    assert result['metadata']['title'] == 'Synthetic document'
    assert result['pages'] == [{'page_num': 1, 'text_content': 'First page contents'}]
    assert read_pdf(path)['full_text'] == 'First page contents\nSecond page contents'
    assert read_pdf(path, max_chars=1)['extraction_truncated']


def test_rat_digital_fallback_keeps_page_markers(tmp_path, monkeypatch):
    from rat.crawler import extractors
    path = tmp_path / 'test.pdf'
    make_pdf(path)
    monkeypatch.setattr(extractors.platform, 'system', lambda: 'Linux')
    text = extractors.extract_text_from_pdf(str(path))
    assert 'Title: Synthetic document' in text
    assert '--- Page 2 ---\nSecond page contents' in text
    assert extractors.extract_text_from_pdf(str(tmp_path / 'missing.pdf')) == ''


def test_tesseract_preserves_boxes_confidence_and_falls_back(tmp_path, monkeypatch):
    from document_intake import tesseract
    path = tmp_path / 'image.png'
    path.touch()
    tsv = 'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
    tsv += '5\t1\t1\t1\t1\t1\t10\t20\t30\t40\t90\tTotal\n'
    tsv += '5\t1\t2\t1\t1\t1\t10\t70\t30\t40\t95\t110000\n'
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return NS(returncode=0, stdout=tsv)
    monkeypatch.setattr(tesseract.subprocess, 'run', run)
    result = TesseractOCREngine(timeout=2).run_ocr(str(path))
    assert result['tokens'][0]['bbox'] == [10, 20, 40, 60]
    assert result['tokens'][0]['confidence'] == .9
    assert result['full_text'] == 'Total\n110000'
    assert calls[0][1]['timeout'] == 2 and 'vie+eng' in calls[0][0]
    outputs = iter([NS(returncode=1, stdout=''), NS(returncode=0, stdout='Fallback text')])
    monkeypatch.setattr(tesseract.subprocess, 'run', lambda *a, **k: next(outputs))
    assert TesseractOCREngine().run_ocr(str(path))['full_text'] == 'Fallback text'
    assert TesseractOCREngine().run_ocr(str(tmp_path / 'missing'))['tokens'] == []


@pytest.mark.parametrize('as_bytes', [False, True])
def test_vision_shared_coordinates_and_bytes(tmp_path, monkeypatch, as_bytes):
    from document_intake import vision
    path = tmp_path / 'image.png'
    Image.new('RGB', (200, 100)).save(path)
    candidate = NS(string=lambda: ' Total ', confidence=lambda: .8)
    box = NS(origin=NS(x=.1, y=.2), size=NS(width=.5, height=.3))
    observation = NS(topCandidates_=lambda n: [candidate], boundingBox=lambda: box)
    request = NS(setRecognitionLevel_=lambda x: None, setUsesLanguageCorrection_=lambda x: None,
                 setRecognitionLanguages_=lambda x: None, results=lambda: [observation])
    handler = NS(performRequests_error_=lambda *a: True)
    req_cls = NS(alloc=lambda: NS(init=lambda: request))
    handler_cls = NS(alloc=lambda: NS(initWithData_options_=lambda *a: handler,
                                     initWithURL_options_=lambda *a: handler))
    monkeypatch.setattr(vision.platform, 'system', lambda: 'Darwin')
    monkeypatch.setitem(sys.modules, 'objc', NS(loadBundle=lambda *a, **k: None,
                        lookUpClass=lambda name: req_cls if name == 'VNRecognizeTextRequest' else handler_cls))
    monkeypatch.setitem(sys.modules, 'Foundation', NS(NSURL=NS(fileURLWithPath_=lambda x: x)))
    assert vision.recognize_tokens(path.read_bytes() if as_bytes else path) == [
        {'text': 'Total', 'confidence': .8, 'bbox': [20, 50, 120, 80]}]


def test_scanned_pdf_uses_shared_vision(tmp_path, monkeypatch):
    from document_intake import pdf, vision
    page = NS(string=lambda: '', thumbnailOfSize_forBox_=lambda *a: NS(TIFFRepresentation=lambda: b'image'))
    doc = NS(documentAttributes=lambda: {}, pageCount=lambda: 1, pageAtIndex_=lambda i: page)
    cls = NS(alloc=lambda: NS(initWithURL_=lambda x: doc))
    monkeypatch.setitem(sys.modules, 'objc', NS(loadBundle=lambda *a, **k: None, lookUpClass=lambda x: cls))
    monkeypatch.setitem(sys.modules, 'Foundation', NS(NSURL=NS(fileURLWithPath_=lambda x: x), NSSize=lambda *a: a))
    monkeypatch.setattr(pdf.os.path, 'exists', lambda x: True)
    monkeypatch.setattr(vision, 'recognize_tokens', lambda data: [{'text': 'Scanned content'}] if data == b'image' else [])
    assert pdf.read_pdf_native('synthetic.pdf') == '--- Page 1 (Scanned OCR) ---\nScanned content'


def test_shared_import_does_not_load_apps_or_optional_engines():
    script = "import sys; import document_intake.pdf, document_intake.vision, document_intake.tesseract; "
    script += "assert not any(n in sys.modules for n in ('rat', 'nesy_docai', 'z3', 'objc', 'pypdf', 'PIL', 'PyQt6'))"
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
