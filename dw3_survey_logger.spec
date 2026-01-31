# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for DW3 Survey Logger
#
# Build with:
#   py -m PyInstaller --noconfirm --clean dw3_survey_logger.spec

import os

# Always resolve paths relative to this spec file (CI-proof)
ROOT = os.path.dirname(os.path.abspath(__file__))

a = Analysis(
    ['main.py'],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'assets'), 'assets'),
        (os.path.join(ROOT, 'templates'), 'templates'),
    ],
    # Keep hiddenimports minimal: only modules PyInstaller sometimes misses
    hiddenimports=[
        'pynput',
        'pynput.keyboard',
        'pynput.keyboard._win32',
        'openpyxl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DW3 Survey Logger',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.join(ROOT, 'assets', 'earth2.ico'),
)
