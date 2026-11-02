"""Copy the pinned multilingual embedding model into rat/assets/embedding for bundling.

Never downloads: it copies an existing fastembed cache (default: the system temp
fastembed_cache) into a symlink-free Hugging Face cache layout and checks every
file against tools/rat_embedding_model.lock.json. Pass --write-lock once to pin a
newly reviewed copy.

    python tools/prepare_rat_embedding_model.py [--cache DIR] [--write-lock]
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = 'models--qdrant--paraphrase-multilingual-MiniLM-L12-v2-onnx-Q'
DEST = ROOT / 'rat/assets/embedding'
LOCK = ROOT / 'tools/rat_embedding_model.lock.json'


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def quantize_onnx_int8(onnx_path: Path):
    """Dynamically quantize an ONNX model to INT8 (converts FP16 weights to FP32 first if needed)."""
    try:
        import numpy as np
        import onnx
        from onnx import numpy_helper, TensorProto
        from onnxruntime.quantization import quantize_dynamic, QuantType
    except ImportError as e:
        sys.exit(f'Quantization requires onnx and onnxruntime: {e}. Install with: pip install onnx')

    model = onnx.load(str(onnx_path))
    has_fp16 = False
    for init in model.graph.initializer:
        if init.data_type == TensorProto.FLOAT16:
            has_fp16 = True
            arr = numpy_helper.to_array(init).astype(np.float32)
            init.CopyFrom(numpy_helper.from_array(arr, name=init.name))
    if has_fp16:
        for n in model.graph.node:
            if n.op_type == 'Cast':
                for attr in n.attribute:
                    if attr.name == 'to' and attr.i == TensorProto.FLOAT16:
                        attr.i = TensorProto.FLOAT
        for vi in model.graph.value_info:
            if vi.type.tensor_type.elem_type == TensorProto.FLOAT16:
                vi.type.tensor_type.elem_type = TensorProto.FLOAT

    with tempfile.TemporaryDirectory() as tmp_dir:
        fp32_path = Path(tmp_dir) / 'model_fp32.onnx'
        onnx.save(model, str(fp32_path))
        quant_path = Path(tmp_dir) / 'model_int8.onnx'
        quantize_dynamic(str(fp32_path), str(quant_path), weight_type=QuantType.QInt8)
        shutil.copyfile(quant_path, onnx_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', default=str(Path(tempfile.gettempdir()) / 'fastembed_cache'))
    parser.add_argument('--quantize-int8', action='store_true', help='dynamically quantize model weights to INT8')
    parser.add_argument('--write-lock', action='store_true')
    parser.add_argument('--check-only', action='store_true', help='verify the prepared copy against the lock')
    args = parser.parse_args()
    if args.check_only:
        target = DEST / MODEL_DIR
        files = {str(p.relative_to(target)): sha256(p) for p in sorted(target.rglob('*')) if p.is_file()} if target.is_dir() else {}
        sys.exit(0 if files and files == json.loads(LOCK.read_text())['files'] else 1)
    source = Path(args.cache) / MODEL_DIR
    revision = (source / 'refs/main').read_text().strip()
    snapshot = source / 'snapshots' / revision
    if not snapshot.is_dir():
        sys.exit(f'No cached snapshot at {snapshot}; load the model once with fastembed first.')
    target = DEST / MODEL_DIR
    shutil.rmtree(target, ignore_errors=True)
    (target / 'refs').mkdir(parents=True)
    (target / 'refs/main').write_text(revision)
    # Dereference blob symlinks so the bundle holds each file once.
    shutil.copytree(snapshot, target / 'snapshots' / revision, symlinks=False)
    if (source / 'files_metadata.json').is_file():
        shutil.copy2(source / 'files_metadata.json', target / 'files_metadata.json')
    if args.quantize_int8:
        onnx_file = target / 'snapshots' / revision / 'model_optimized.onnx'
        if onnx_file.is_file():
            quantize_onnx_int8(onnx_file)
            meta_path = target / 'files_metadata.json'
            if meta_path.is_file():
                meta = json.loads(meta_path.read_text())
                rel_key = str(onnx_file.relative_to(target))
                if rel_key in meta:
                    meta[rel_key]['size'] = onnx_file.stat().st_size
                    meta_path.write_text(json.dumps(meta))
    files = {str(p.relative_to(target)): sha256(p) for p in sorted(target.rglob('*')) if p.is_file()}
    if args.write_lock:
        LOCK.write_text(json.dumps({'model': MODEL_DIR, 'revision': revision, 'license': 'Apache-2.0',
                                    'files': files}, indent=2) + '\n')
    else:
        pinned = json.loads(LOCK.read_text())['files']
        if pinned != files:
            shutil.rmtree(target)
            sys.exit('Copied model does not match tools/rat_embedding_model.lock.json; nothing kept.')
    size = sum(p.stat().st_size for p in target.rglob('*') if p.is_file())
    print(f'Prepared {target} ({size / 1e6:.0f} MB, revision {revision[:8]})')


if __name__ == '__main__':
    main()
