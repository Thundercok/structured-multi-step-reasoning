"""Bundled CPU machine translation behind the shared translation tool.

No downloads, Qt, model loading or native imports at module import time.
Inference uses CTranslate2 and SentencePiece, not an alternate Agent loop.
"""
from pathlib import Path
import hashlib
import json
import re
import sys
import threading

PAIRS = frozenset({('en','vi'), ('vi','en')})


def sentence_units(text):
    """Bounded sentence inputs; preserve separators and common abbreviations."""
    start = 0
    abbreviations = {'mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'etc.', 'e.g.', 'i.e.', 'vs.'}
    for match in re.finditer(r'(?<=[.!?。！？])([ \t]+)(?=\S)', text):
        previous = text[start:match.start()]
        word = previous.split()[-1].casefold() if previous.split() else ''
        if word in abbreviations or re.fullmatch(r'[a-z]\.', word):
            continue
        yield previous, match.group(1)
        start = match.end()
    if start < len(text):
        yield text[start:], ''


def token_batches(tokens, limit=256):
    while tokens:
        end = min(limit, len(tokens))
        if end < len(tokens):
            boundaries = [i for i in range(1,end+1) if tokens[i].startswith('\u2581')]
            if boundaries:
                end = boundaries[-1]
        yield tokens[:end]
        tokens = tokens[end:]


class LocalTranslator:
    def __init__(self, directory=None):
        base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
        self.directory = Path(directory) if directory else base/'rat/assets/translation'
        self._lock = threading.RLock()
        self._pair = self._translator = self._tokenizer = self._info = None

    def _load(self, source, target, cancelled):
        pair = source+'-'+target
        if self._pair == pair:
            return
        if cancelled():
            raise ValueError('cancelled:translation')
        if (source,target) not in PAIRS:
            raise ValueError('translation_local_pair_unavailable')
        try:
            manifest = json.loads((self.directory/'manifest.json').read_text())
            entry = manifest['models'][pair]
            folder = self.directory/pair
            for relative in ('sentencepiece.model','model/config.json','model/model.bin','model/shared_vocabulary.json'):
                if cancelled():
                    raise ValueError('cancelled:translation')
                if hashlib.sha256((folder/relative).read_bytes()).hexdigest() != entry['files'][relative]:
                    raise ValueError('translation_local_integrity_failed')
            import ctranslate2
            import sentencepiece
            if self._translator is not None:
                self._translator.unload_model()
                self._translator = self._tokenizer = self._pair = None
            tokenizer = sentencepiece.SentencePieceProcessor(model_file=str(folder/'sentencepiece.model'))
            compute = 'int8' if 'int8' in ctranslate2.get_supported_compute_types('cpu') else 'float32'
            translator = ctranslate2.Translator(str(folder/'model'), device='cpu',
                compute_type=compute, inter_threads=1, intra_threads=2)
            self._translator, self._tokenizer, self._pair = translator, tokenizer, pair
            self._info = {'id':entry['pair'], 'version':entry['version'],
                'package_sha256':entry['sha256'], 'license':entry['license'],
                'engine':'CTranslate2', 'engine_version':ctranslate2.__version__,
                'device':'cpu', 'compute_type':compute,
                'decoding': {'beam_size':4, 'coverage_penalty':0.2,
                    'sentence_splitter':'punctuation-v1', 'source_token_limit':256}}
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError('translation_local_unavailable') from exc

    @property
    def model_info(self):
        return dict(self._info or {})

    def translate(self, text, source, target, cancelled=lambda:False):
        with self._lock:
            self._load(source,target,cancelled)
            output = []
            for line in re.split(r'(\r\n|\r|\n)',text):
                if cancelled():
                    raise ValueError('cancelled:translation')
                if not line.strip():
                    output.append(line)
                    continue
                leading = line[:len(line)-len(line.lstrip(' \t'))]
                trailing = line[len(line.rstrip(' \t')):]
                rendered = []
                for sentence, separator in sentence_units(line.strip()):
                    pieces = []
                    for tokens in token_batches(self._tokenizer.encode(sentence, out_type=str)):
                        if cancelled():
                            raise ValueError('cancelled:translation')
                        # Beam search requires complete decoding; cancellation is
                        # checked between bounded 256-token source units. Never
                        # silently truncate source or cache a cancelled result.
                        result = self._translator.translate_batch([tokens], beam_size=4,
                            coverage_penalty=0.2, max_input_length=0, max_decoding_length=512)[0]
                        if cancelled():
                            raise ValueError('cancelled:translation')
                        translated = result.hypotheses[0]
                        if len(translated) >= 512:
                            raise ValueError('translation_local_output_limit')
                        pieces.append(self._tokenizer.decode_pieces(translated).replace('\u2581',' ').strip())
                    rendered.append(' '.join(pieces)+separator)
                output.append(leading+''.join(rendered)+trailing)
            return ''.join(output)
