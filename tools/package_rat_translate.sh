#!/bin/zsh
# Standalone, shareable "Rat Dich.app" (arm64) + zip in dist/. Needs the repo .venv with PyInstaller.
set -e
cd "$(cd "$(dirname "$0")/.." && pwd)"
swiftc -O tools/apple_translate.swift -o rat/bin/apple_translate
.venv/bin/python -m PyInstaller --noconfirm --clean --windowed --name "Rat Dich" \
  --icon tools/rat_translate.icns --osx-bundle-identifier vn.rat.translate \
  --add-data "rat/assets/rat_mascot_cutout.png:rat/assets" \
  --add-binary "rat/bin/apple_translate:rat/bin" \
  --collect-data certifi \
  --hidden-import document_intake.vision --hidden-import objc --hidden-import Foundation \
  --paths . rat/ui/mini_translate.py
APP="dist/Rat Dich.app"
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$APP/Contents/Info.plist"
codesign --force --deep --sign - "$APP"   # ad-hoc: friend must right-click > Open once
(cd dist && rm -f "Rat Dich.zip" && ditto -c -k --keepParent "Rat Dich.app" "Rat Dich.zip")
echo "Built: $PWD/dist/Rat Dich.zip"
