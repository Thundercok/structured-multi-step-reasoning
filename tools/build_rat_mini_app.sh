#!/bin/zsh
# Standalone Qt Quick Mini. Never installs dependencies or downloads models.
# Prepare pinned data once with tools/prepare_rat_translation_models.py.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
DIST_DIR="${RAT_MINI_DIST_DIR:-$ROOT/dist}"
BUILD_TMP="$(mktemp -d /private/tmp/rat-mini-app.XXXXXX)"
trap 'rm -rf "$BUILD_TMP"' EXIT
export CLANG_MODULE_CACHE_PATH="$BUILD_TMP/clang-cache"
export SWIFT_MODULECACHE_PATH="$BUILD_TMP/swift-cache"
export PYINSTALLER_CONFIG_DIR="$BUILD_TMP/pyinstaller-cache"
if [[ -n "${RAT_MINI_SPIKE_DEPS:-}" ]]; then
  export PYTHONPATH="$RAT_MINI_SPIKE_DEPS${PYTHONPATH:+:$PYTHONPATH}"
fi
cd "$ROOT"
if [[ ! -f "$ROOT/rat/assets/translation/en-vi/model/model.bin" || ! -f "$ROOT/rat/assets/translation/vi-en/model/model.bin" ]]; then
  echo 'Prepare bundled translation data with tools/prepare_rat_translation_models.py before building.' >&2
  exit 1
fi
excluded=(torch transformers fastembed scipy sklearn gymnasium mlx mlx_lm sentence_transformers
  onnxruntime apsw sqlite_vec rat.engine.mini_semantic
  rat.engine.selected_document_qa rat.engine.selected_pdf rat.engine.qa_engine rat.engine.meta_reasoner
  rat.ui.quick_pdf_controller rat.ui.quick_app reasoning experiments
  PyQt6.QtWidgets rat.ui.mini_floaty rat.ui.mini_settings_dialog
  matplotlib pandas IPython ipykernel notebook jupyterlab bokeh plotly seaborn dask sympy onnx
  rat.timetable rat.astrology rat.plugins rat.crawler rat.engine.slm rat.engine.document_model_service
  rat.kernel.capabilities.applications rat.kernel.capabilities.documents
  rat.kernel.capabilities.result_tables rat.kernel.capabilities.smart_notes rat.kernel.capabilities.web
  rat.kernel.capabilities.timetable rat.kernel.capabilities.natal rat.kernel.capabilities.views)
exclude_args=()
for module in "${excluded[@]}"; do exclude_args+=(--exclude-module "$module"); done
PYTHON_BIN="$PYTHON_BIN" zsh "$ROOT/tools/build_rat_mini_hotkey.sh" "$BUILD_TMP/rat-hotkey"
rm -rf "$DIST_DIR/RAT Mini" "$DIST_DIR/RAT Mini.app" "$DIST_DIR/RAT Mini.zip"
"$PYTHON_BIN" -m PyInstaller --noconfirm --clean --windowed --name "RAT Mini" \
  --distpath "$DIST_DIR" --workpath "$BUILD_TMP/build" --specpath "$BUILD_TMP/spec" \
  --icon "$ROOT/tools/rat_translate.icns" --osx-bundle-identifier vn.rat.mini \
  --add-data "$ROOT/rat/assets/rat_mascot_cutout.png:rat/assets" \
  --add-binary "$BUILD_TMP/rat-hotkey:rat/bin" \
  --add-data "$ROOT/rat/assets/translation:rat/assets/translation" \
  --add-data "$ROOT/rat/ui/quick/MiniDesk.qml:rat/ui/quick" \
  --add-data "$ROOT/rat/ui/quick/SpeechSurface.qml:rat/ui/quick" \
  --add-data "$ROOT/rat/ui/quick/MascotPose.qml:rat/ui/quick" \
  --add-data "$ROOT/rat/ui/quick/QuietButton.qml:rat/ui/quick" \
  --add-data "$ROOT/rat/ui/quick/DeskIcon.qml:rat/ui/quick" \
  --collect-data certifi \
  --copy-metadata ctranslate2 --copy-metadata sentencepiece --copy-metadata numpy \
  --collect-data rfc3987_syntax --collect-data lark --collect-data jsonschema_specifications \
  --hidden-import objc --hidden-import Foundation \
  --hidden-import AppKit --hidden-import Quartz --hidden-import ApplicationServices --hidden-import document_intake.vision --hidden-import document_intake.pdf \
  --hidden-import ctranslate2 --hidden-import sentencepiece \
  "${exclude_args[@]}" --paths "$ROOT" "$ROOT/mini_app.py"
export RAT_MINI_HOTKEY_BINARY="$BUILD_TMP/rat-hotkey"
export RAT_MINI_BUILT_APP="$DIST_DIR/RAT Mini.app"
# PyInstaller can continue after its Qt discovery subprocess aborts. Never
# publish a bundle missing the platform plugin required to open any window.
if [[ ! -f "$RAT_MINI_BUILT_APP/Contents/Frameworks/PyQt6/Qt6/plugins/platforms/libqcocoa.dylib" ]]; then
  echo 'Build failed: Qt Cocoa platform plugin was not collected.' >&2
  exit 1
fi
"$PYTHON_BIN" - <<'PY'
import os,plistlib,hashlib,json,subprocess
from pathlib import Path
from rat.engine.mini_version import BUILD, VERSION
p=Path(os.environ['RAT_MINI_BUILT_APP'])/'Contents/Info.plist'
data=plistlib.loads(p.read_bytes())
data.update(LSUIElement=True,LSMinimumSystemVersion='14.0',CFBundleShortVersionString=VERSION,CFBundleVersion=BUILD,
            NSDocumentsFolderUsageDescription='RAT Mini tìm và mở file trong Documents khi bạn yêu cầu và chọn thư mục này.',
            NSDesktopFolderUsageDescription='RAT Mini tìm file trên Desktop và đọc ảnh chụp màn hình bạn chủ động đưa vào app.',
            NSDownloadsFolderUsageDescription='RAT Mini tìm và mở file trong Downloads khi bạn yêu cầu và chọn thư mục này.',
            NSScreenCaptureUsageDescription='RAT Mini nhận chữ trong vùng màn hình bạn chọn để dịch.',
            NSAppleEventsUsageDescription='RAT Mini sao chép chữ đang chọn khi bạn yêu cầu.')
p.write_bytes(plistlib.dumps(data))
manifest = dict(build=BUILD, version=VERSION, protocol='SELECT2',
    source_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    source_dirty=bool(subprocess.check_output(['git','status','--porcelain','--','rat','tools'],text=True).strip()),
    helper_sha256=hashlib.sha256(Path(os.environ['RAT_MINI_HOTKEY_BINARY']).read_bytes()).hexdigest(),
    acceptance='not_run_by_packaging')
(Path(os.environ['RAT_MINI_BUILT_APP'])/'Contents/Resources/rat-lite-build.json').write_text(json.dumps(manifest,indent=2))

PY
RAT_CODESIGN_IDENTITY="${RAT_CODESIGN_IDENTITY:--}"
codesign --force --deep --sign "$RAT_CODESIGN_IDENTITY" "$RAT_MINI_BUILT_APP"
rm -rf "$DIST_DIR/RAT Mini"
ditto -c -k --keepParent "$RAT_MINI_BUILT_APP" "$DIST_DIR/RAT Mini.zip"
"$PYTHON_BIN" - <<'PY'
from pathlib import Path
import zipfile
import os
root = Path.cwd()
with zipfile.ZipFile(Path(os.environ['RAT_MINI_BUILT_APP']).parent / 'RAT Mini.zip', 'a', compression=zipfile.ZIP_DEFLATED) as package:
    package.write(root / 'docs/RAT_MINI_BAT_DAU.txt', 'BAT DAU O DAY.txt')
    package.write(Path(os.environ['RAT_MINI_BUILT_APP'])/'Contents/Resources/rat-lite-build.json', 'RAT Lite build.json')
    cmd_script = '#!/bin/zsh\nDIR="$(cd "$(dirname "$0")" && pwd)"\nxattr -cr "$DIR/RAT Mini.app" 2>/dev/null || true\nopen "$DIR/RAT Mini.app"\n'
    cmd_info = zipfile.ZipInfo('Mo RAT Mini Lan Dau.command')
    cmd_info.external_attr = 0o755 << 16
    package.writestr(cmd_info, cmd_script)
PY
echo "Built: $DIST_DIR/RAT Mini.zip"
