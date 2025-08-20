# -*- mode: python ; coding: utf-8 -*-
# CIF Checker v2.0 PyInstaller Specification
# Optimized for standalone executable distribution

import sys
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Collect additional data files for PyQt6
pyqt6_datas = collect_data_files('PyQt6')

a = Analysis(
    ['src/main.py'],  # Main script path
    pathex=[],
    binaries=[
        # Force inclusion of Python DLL for better compatibility
        # This helps resolve issues where users can't run the .exe
        (sys.executable.replace('python.exe', 'python*.dll'), '.'),
    ],
    datas=[
        # Core CIF dictionary (essential for field validation)
        ('cif_core.dic', '.'),
        
        # GUI configuration and field definitions
        ('src/gui/field_definitions.cif_ed', 'gui'),
        ('src/gui/field_definitions.cif_hp', 'gui'), 
        ('src/gui/field_definitions_all.cif_defs', 'gui'),
        ('src/gui/field_definitions_issues.cif_defs', 'gui'),
        ('src/gui/editor_settings.json', 'gui'),
        
        # Include PyQt6 data files for better compatibility
    ] + pyqt6_datas,
    hiddenimports=[
        # Core PyQt6 modules
        'PyQt6.QtWidgets',
        'PyQt6.QtCore', 
        'PyQt6.QtGui',
        
        # Additional modules that might be imported dynamically
        'PyQt6.QtSvg',
        'PyQt6.sip',
        
        # Python standard library modules used by our code
        'json',
        'os',
        'sys',
        'pathlib',
        're',
        'typing',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'matplotlib',
        'numpy', 
        'pandas',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CIF_Checker_v2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress executable (set to False if causing issues)
    upx_exclude=[
        'vcruntime140.dll',  # Don't compress Visual C++ runtime
        'python*.dll',       # Don't compress Python DLL
    ],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging if needed
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico'  # Uncomment and add icon file if available
)
