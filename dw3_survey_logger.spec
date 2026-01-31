# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for DW3 Survey Logger
#
# Build with:
#   python -m PyInstaller --noconfirm --clean dw3_survey_logger.spec

import os

# __file__ is set by PyInstaller to the absolute path of this spec file
ROOT = os.path.dirname(os.path.abspath(SPECPATH))

a = Analysis(
    [os.path.join(ROOT, 'main.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'assets'), 'assets'),
        (os.path.join(ROOT, 'templates'), 'templates'),
    ],
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
    strip=False,
    upx=True,
    console=False,
    icon=os.path.join(ROOT, 'assets', 'earth2.ico'),
)
