# -*- mode: python ; coding: utf-8 -*-

import os


a = Analysis(
    ['downloader.py'],
    pathex=[],
    binaries=[],
    datas=[
        (os.path.join('assets', 'images', 'icon.png'), os.path.join('assets', 'images')),
        (os.path.join('assets', 'images', 'icon.ico'), os.path.join('assets', 'images')),
    ],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='Multi-Downloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join('assets', 'images', 'icon.ico'),
)
