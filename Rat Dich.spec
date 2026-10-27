# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [('rat/assets/rat_mascot_cutout.png', 'rat/assets')]
datas += collect_data_files('certifi')


a = Analysis(
    ['rat/ui/mini_translate.py'],
    pathex=['.'],
    binaries=[('rat/bin/apple_translate', 'rat/bin')],
    datas=datas,
    hiddenimports=['document_intake.vision', 'objc', 'Foundation'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Rat Dich',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['tools/rat_translate.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Rat Dich',
)
app = BUNDLE(
    coll,
    name='Rat Dich.app',
    icon='tools/rat_translate.icns',
    bundle_identifier='vn.rat.translate',
)
