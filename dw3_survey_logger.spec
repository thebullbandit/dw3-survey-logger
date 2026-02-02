# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for DW3 Survey Logger
#
# Build with:
#   python -m PyInstaller --noconfirm --clean dw3_survey_logger.spec

a = Analysis(
    ['main.py'],
    datas=[
        ('assets', 'assets'),
        ('templates', 'templates'),
    ],
    hiddenimports=[
        'pynput',
        'pynput.keyboard',
        'pynput.keyboard._win32',
        'openpyxl',
        'diagnostics_exporter',
        'density_worksheet_exporter_multi_file',
        'win32api',
        'win32gui',
        'win32con',
        'win32process',
    ],
    hookspath=[],
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
    icon='assets/earth2.ico',
)
