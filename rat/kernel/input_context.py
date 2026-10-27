"""Headless trusted image ingress shared by RAT clients, outside model arguments."""
from dataclasses import dataclass, field
import hashlib
import re
from uuid import uuid4

MAX_IMAGE_BYTES = 12_000_000
MAX_IMAGE_PIXELS = 25_000_000
IMAGE_ORIGINS = frozenset({'selected_file', 'dropped_file', 'dropped_image', 'clipboard_file', 'clipboard_image', 'legacy_image_bytes', 'screen_region'})


@dataclass(frozen=True)
class ImageInput:
    content: bytes = field(repr=False)
    origin: str
    source_file_sha256: str | None = None
    input_id: str = field(default_factory=lambda: 'img-' + uuid4().hex)
    content_sha256: str = field(init=False)

    def __post_init__(self):
        if not isinstance(self.content, bytes) or not 0 < len(self.content) <= MAX_IMAGE_BYTES:
            raise ValueError('image_input_invalid: Ảnh trống hoặc quá lớn.')
        if self.origin not in IMAGE_ORIGINS:
            raise ValueError('image_origin_invalid')
        if self.source_file_sha256 is not None and (not isinstance(self.source_file_sha256, str)
                or not re.fullmatch('[0-9a-f]{64}', self.source_file_sha256)):
            raise ValueError('image_source_digest_invalid')
        if not isinstance(self.input_id, str) or not re.fullmatch('img-[0-9a-f]{32}', self.input_id):
            raise ValueError('image_input_id_invalid')
        object.__setattr__(self, 'content_sha256', hashlib.sha256(self.content).hexdigest())

    def provenance(self):
        return {'version': 1, 'input_id': self.input_id, 'kind': 'image',
            'origin': self.origin, 'content_sha256': self.content_sha256,
            'byte_count': len(self.content), 'source_file_sha256': self.source_file_sha256}
