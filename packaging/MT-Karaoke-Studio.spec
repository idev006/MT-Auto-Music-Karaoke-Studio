# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir contract for the portable Windows desktop application."""

from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).parent

datas = [
    (str(PROJECT_ROOT / "assets"), "assets"),
    (str(PROJECT_ROOT / "migrations"), "migrations"),
    (str(PROJECT_ROOT / "alembic.ini"), "."),
    (str(PROJECT_ROOT / "config" / "openrouter.env.example"), "config"),
]

analysis = Analysis(
    [str(PROJECT_ROOT / "src" / "mt_engine" / "ui" / "app.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "ruff",
        "tensorflow",
        "torch",
        "torchaudio",
        "torchvision",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="MT-Karaoke-Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MT-Karaoke-Studio",
)
