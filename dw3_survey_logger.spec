# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for DW3 Survey Logger
#
# Build with:
#   pyinstaller dw3_survey_logger.spec

import os

block_cipher = None
ROOT = os.path.abspath('.')

a = Analysis(
    ['main.py'],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'assets'), 'assets'),
        (os.path.join(ROOT, 'templates'), 'templates'),
    ],
    hiddenimports=[
        'earth_similarity_score',
        'density_worksheet_exporter',
        'hotkey_manager',
        'observer_models',
        'observer_storage',
        'observer_overlay',
        'journal_state_manager',
        'journal_monitor',
        'import_journals',
        'earth2_database',
        'update_checker',
        'window_focus',
        'pynput',
        'pynput.keyboard',
        'pynput.keyboard._win32',
        'openpyxl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
