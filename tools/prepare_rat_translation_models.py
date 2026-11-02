"""Developer packaging step. Recipient app never downloads or installs code/models."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import ssl
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def prepare(archives, destination, download=False):
    lock = json.loads((ROOT/'tools/rat_translation_models.lock.json').read_text())
    archives.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {'schema_version': 1, 'engine': lock['runtime'], 'models': {}}
    for entry in lock['models']:
        pair = entry['pair']
        package = archives/(pair.replace('-', '_')+'-'+entry['version']+'.argosmodel')
        if not package.exists() and download:
            import certifi
            temporary = package.with_suffix('.partial')
            try:
                with urllib.request.urlopen(entry['url'], timeout=30,
                        context=ssl.create_default_context(cafile=certifi.where())) as response, temporary.open('wb') as output:
                    count = 0
                    while piece := response.read(1024*1024):
                        count += len(piece)
                        if count > entry['bytes']:
                            raise ValueError('Model download exceeds pinned size')
                        output.write(piece)
                temporary.replace(package)
            finally:
                temporary.unlink(missing_ok=True)
        if not package.exists() or package.stat().st_size != entry['bytes'] or hashlib.sha256(package.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Missing or mismatched pinned model: '+pair)
        files = {}
        with zipfile.ZipFile(package) as archive:
            # Copy only the inference data. No pickle/Stanza/PyTorch payloads.
            for relative in ('sentencepiece.model','metadata.json','README.md',
                    'model/config.json','model/model.bin','model/shared_vocabulary.json'):
                member = entry['archive_prefix']+'/'+relative
                if archive.getinfo(member).file_size > 200_000_000:
                    raise ValueError('Oversized model member')
                target = destination/pair/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open('wb') as output:
                    shutil.copyfileobj(source, output)
                files[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest['models'][pair] = {**entry, 'files': files}
    (destination/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (destination/'ATTRIBUTION.txt').write_text(
        'OPUS-MT language models, packaged by Argos Open Technologies.\n'
        'Jörg Tiedemann and Santhosh Thottingal (2020).\n'
        'OPUS-MT — Building open translation services for the World. EAMT 2020.\n'
        'Models licensed CC-BY-4.0: https://creativecommons.org/licenses/by/4.0/\n'
        'Source: https://www.argosopentech.com/argospm/index/\n'
        'RAT omits Stanza data and runs the unchanged int8 CTranslate2 model files.\n'
        'Exact package URLs, hashes and per-file hashes: manifest.json.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archives', type=Path, default=ROOT/'artifacts/rat_mini_local_mt_20261027/downloads')
    parser.add_argument('--destination', type=Path, default=ROOT/'rat/assets/translation')
    parser.add_argument('--download', action='store_true')
    options = parser.parse_args()
    prepare(options.archives, options.destination, options.download)
