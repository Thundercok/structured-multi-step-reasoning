# -*- mode: python ; coding: utf-8 -*-
"""
rat.spec — PyInstaller bundle specification for macOS Standalone App.
Packages Python runtime, PyQt6, ONNX/FastEmbed, Apple Vision, and all dependencies into a single rat.app.
"""

import sys
from pathlib import Path

block_cipher = None

added_files = [
    ('rat/crawler', 'rat/crawler'),
    ('rat/engine', 'rat/engine'),
    ('rat/ui', 'rat/ui'),
    ('rat/assets', 'rat/assets'),
    ('rat/os', 'rat/os'),
    ('rat/timetable', 'rat/timetable'),
]

hidden_imports = [
    'rat.os.crash_shield',
    'rat.os.memory_sentinel',
    'rat.os.hotkey',
    'rat.os.shell_integration',
    'rat.os.daemon',
    'rat.os.menu_bar',
    'rat.os.app',
    'rat.timetable',
    'rat.timetable.model',
    'rat.timetable.compositor',
    'rat.timetable.data',
    'rat.ui.schedule_window',
    'rat.ui.omnibar',
    'rat.ui.chat_stream',
    'rat.ui.claude_widget',
    'rat.engine.meta_reasoner',
    'pynput',
    'pynput.keyboard',
    'pynput.keyboard._darwin',
    'pynput._util',
    'pynput._util.darwin',
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'pypdf',
    'docx',
    'pptx',
    'openpyxl',
    'fastembed',
    'onnxruntime',
    'tokenizers',
    'objc',
    'Foundation',
    'Quartz',
    'AppKit',
    'ApplicationServices',
    'watchdog',
    'numpy',
    'PIL',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pytest',
        'torch',
        'torchvision',
        'torchaudio',
        'transformers',
        'cv2',
        'pandas',
        'sklearn',
        'scipy',
        'sympy',
        'IPython',
        'jedi',
        'tests',
        'tornado',
        'twisted',
        'selenium',
        'playwright',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='rat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='rat',
)

app = BUNDLE(
    coll,
    name='rat.app',
    icon='rat.icns',
    bundle_identifier='com.thundercock.rat',
    info_plist={
        'CFBundleName': 'rat',
        'CFBundleDisplayName': 'rat — Smart File Finder',
        'CFBundleGetInfoString': "AI-Powered Local Semantic File Finder for macOS",
        'CFBundleIdentifier': "com.thundercock.rat",
        'CFBundleVersion': "1.0.0",
        'CFBundleShortVersionString': "1.0.0",
        'NSHumanReadableCopyright': "Copyright © 2026, All Rights Reserved.",
        'NSHighResolutionCapable': True,
        'NSSupportsAutomaticGraphicsSwitching': True,
        'LSMinimumSystemVersion': '12.0',
        'NSAppleEventsUsageDescription': "rat requires AppleEvents access to open files and navigate system apps quickly.",
        'NSDesktopFolderUsageDescription': "rat indexes files in Desktop for instant semantic search.",
        'NSDocumentsFolderUsageDescription': "rat indexes documents for instant semantic search.",
        'NSDownloadsFolderUsageDescription': "rat indexes downloads for instant semantic search.",
    },
)
