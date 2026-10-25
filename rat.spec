# -*- mode: python ; coding: utf-8 -*-
"""
rat.spec — PyInstaller bundle specification for macOS Standalone App.
Packages Python runtime, PyQt6, ONNX/FastEmbed, Apple Vision, and all dependencies into a single rat.app.
"""

import sys
import os
from importlib.util import find_spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

project_dir = Path(SPECPATH)
block_cipher = None

# Python modules belong in PYZ, not as duplicate source/__pycache__ directories.
added_files = [
    ('rat/assets', 'rat/assets'),
    ('rat/ui/quick', 'rat/ui/quick'),
    ('rat/engine/snapshot.schema.json', 'rat/engine'),
    ('rat/astrology/ephemeris', 'rat/astrology/ephemeris'),
]

# Collect installed MLX runtime libraries/kernels, never local model directories.
mlx_binaries = collect_dynamic_libs('mlx') if find_spec('mlx') is not None else []
mlx_data = collect_data_files('mlx', includes=['**/*.metallib']) if mlx_binaries else []
format_data = collect_data_files('rfc3987_syntax', includes=['*.lark']) if find_spec('rfc3987_syntax') is not None else []
format_data += collect_data_files('lark', includes=['grammars/*.lark']) if find_spec('lark') is not None else []

hidden_imports = [
    'reasoning',
    'reasoning.entry_predictor',
    'reasoning.optimal_stopping',
    'reasoning.reasoning_env',
    'reasoning.reasoning_strategies',
    'document_intake.pdf',
    'document_intake.vision',
    'document_intake.tesseract',
    'sklearn',
    'scipy',
    'gymnasium',
    'rat.os.crash_shield',
    'rat.os.memory_sentinel',
    'rat.os.hotkey',
    'rat.os.shell_integration',
    'rat.os.daemon',
    'rat.os.menu_bar',
    'rat.os.native_menu',
    'rat.os.native_menu',
    'rat.os.app',
    'rat.timetable',
    'rat.timetable.model',
    'rat.timetable.compositor',
    'rat.timetable.data',
        'rat.engine.persona',
        'rat.engine.work_notes',
        'rat.engine.work_trace',
    'rat.kernel.capabilities.views',
    'rat.astrology.export',
    'rat.engine.meta_reasoner',
    'rat.engine.selected_document_qa',
    'rat.astrology.chart',
    'rat.astrology.places',
    'rat.astrology.svg',
    'swisseph',
    'pynput',
    'pynput.keyboard',
    'pynput.keyboard._darwin',
    'pynput._util',
    'pynput._util.darwin',
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtSvg',
    'PyQt6.QtQml',
    'PyQt6.QtQuick',
    'PyQt6.QtQuickControls2',
    'rat.ui.quick_app',
    'rat.ui.quick_pdf_controller',
    'rat.ui.icon_provider',
    'rat.engine.contradiction_auditor',
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
    [str(project_dir / 'main.py')],
    pathex=[str(project_dir)],
    binaries=mlx_binaries,
    datas=[(str(project_dir / source), target) for source, target in added_files] + mlx_data + format_data,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt6.QtWidgets',
        'tkinter',
        'matplotlib',
        'pytest',
        'torch',
        'torchvision',
        'torchaudio',
        'transformers',
        'cv2',
        'pandas',
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
    argv_emulation=False,
    target_arch=None,
    codesign_identity=os.environ.get('RAT_CODESIGN_IDENTITY') or None,
    entitlements_file=str(project_dir / 'entitlements.plist'),
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
    icon=str(project_dir / 'rat.icns'),
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
