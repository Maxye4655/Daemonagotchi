# -*- mode: python ; coding: utf-8 -*-
# Build with: ./venv/bin/pyinstaller daemonagotchi.spec --noconfirm

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# Textual ships CSS/data files and loads widgets dynamically,
# so it must be collected completely. instructor/openai/pydantic
# use dynamic imports that static analysis can miss.
for package in ("textual", "instructor", "openai", "pydantic"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ["tui.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="daemonagotchi",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
