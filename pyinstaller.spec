# PyInstaller spec for Work Tracker (GUI)
# Build with: pyinstaller pyinstaller.spec

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Use current working directory since __file__ may be undefined when exec'd
project_dir = os.getcwd()
assets_src = os.path.join('work_tracker', 'assets')

# Bundle assets folder
_datas = []
if os.path.isdir(assets_src):
    for fname in os.listdir(assets_src):
        _datas.append((os.path.join(assets_src, fname), assets_src))

hidden = []
# Ensure package modules are discovered
hidden += collect_submodules('work_tracker')

a = Analysis(
    ['main.py'],
    pathex=[project_dir],
    binaries=[],
    datas=_datas,
    hiddenimports=hidden,
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
    [],
    exclude_binaries=True,
    name='work_tracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=(os.path.join('work_tracker', 'assets', 'icon.ico') if os.path.exists(os.path.join('work_tracker','assets','icon.ico')) else None),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='work_tracker',
)
