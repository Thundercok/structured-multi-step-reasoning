"""Apple Vision OCR with text, confidence and top-left pixel coordinates.

Optional frameworks load only when OCR is requested. No Swift compilation or
writes into installed package directories are needed.
"""
import io
import logging
import platform
from pathlib import Path

logger = logging.getLogger(__name__)


def recognize_tokens(source):
    if platform.system() != "Darwin":
        return []
    try:
        import objc
        from Foundation import NSURL
        from PIL import Image
        objc.loadBundle("Vision", globals(), bundle_path="/System/Library/Frameworks/Vision.framework")
        request = objc.lookUpClass("VNRecognizeTextRequest").alloc().init()
        request.setRecognitionLevel_(1)
        request.setUsesLanguageCorrection_(True)
        try:
            request.setRecognitionLanguages_(["vi-VN", "en-US"])
        except Exception:
            pass
        handler_cls = objc.lookUpClass("VNImageRequestHandler")
        if isinstance(source, bytes):
            image_source = io.BytesIO(source)
            handler = handler_cls.alloc().initWithData_options_(source, {})
        else:
            path = Path(source).resolve()
            if not path.is_file():
                return []
            image_source = str(path)
            handler = handler_cls.alloc().initWithURL_options_(NSURL.fileURLWithPath_(str(path)), {})
        with Image.open(image_source) as image:
            width, height = image.size
        if not handler.performRequests_error_([request], None):
            return []
        tokens = []
        for observation in request.results() or []:
            candidates = observation.topCandidates_(1)
            if not candidates:
                continue
            candidate = candidates[0]
            text = str(candidate.string()).strip()
            if not text:
                continue
            box = observation.boundingBox()
            x = int(box.origin.x * width)
            y = int((1 - box.origin.y - box.size.height) * height)
            tokens.append({"text": text, "confidence": float(candidate.confidence()),
                           "bbox": [x, y, x + int(box.size.width * width), y + int(box.size.height * height)]})
        return tokens
    except Exception as exc:
        logger.debug("Apple Vision OCR failed: %s", exc)
        return []
