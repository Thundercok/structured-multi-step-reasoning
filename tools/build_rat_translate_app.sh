#!/bin/zsh
# Build "Rat Dịch.app": a thin launcher bundle (no Dock icon) that runs rat.ui.mini_translate
# with this checkout's .venv. Not a standalone binary: moving/deleting the repo breaks it.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${1:-$HOME/Applications}/Rat Dịch.app"
rm -rf "$APP"; mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
ICONSET="$(mktemp -d)/rat.iconset"; mkdir "$ICONSET"
for s in 16 32 64 128 256 512; do
  sips -z $s $s -s format png "$ROOT/rat/assets/rat_mascot_bust.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/rat.icns"
cat > "$APP/Contents/Info.plist" <<P
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
<key>CFBundleName</key><string>Rat Dịch</string>
<key>CFBundleIdentifier</key><string>vn.rat.translate</string>
<key>CFBundleExecutable</key><string>rat-translate</string>
<key>CFBundleIconFile</key><string>rat</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSUIElement</key><true/>
</dict></plist>
P
cat > "$APP/Contents/MacOS/rat-translate" <<L
#!/bin/zsh
cd "$ROOT"
exec arch -arm64 "$ROOT/.venv/bin/python" -m rat.ui.mini_translate
L
chmod +x "$APP/Contents/MacOS/rat-translate"
echo "Built: $APP"
